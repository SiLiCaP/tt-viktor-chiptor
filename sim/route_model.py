"""ML-KEM-512 exchange time for every chip route (NTT and/or Keccak on the chip, any core), including the
RP2350's cost of feeding the chip. Extends the team's research/sha3/mlkem_model.py (sha3-asic-research):
same hash calls (FIPS 203), same chip clock counts per call, same 300-cycle setup per call.

    python3 sim/route_model.py

What it adds:
  - the K = 2 ring core and the latch core (clocks per permutation measured by the team: 368 / 760 / 1,544 / 1,464)
  - the NTT either in RP2350 software (cited pqm4 cycles) or on the chip (sim/perf_model.py: firmware as written,
    or the optimized what-if)
  - the RP2350's work to drive the hash words, with the firmware as written (per word ~23 cycles to build, per
    returned byte ~15 to unpack; sim/config.py fw_* estimates) or an optimized PIO path where the PIO inserts the
    hash flag bits and DMA moves raw bytes (~2 cycles per word and byte, ESTIMATE)
  - the hash-only chip (chipathon-2026 branch sha3-only): byte words at any K, BURST squeeze (one host word per
    block instead of one per byte) and SamplePolyCBD on chip (the PRF's CBD leaves the RP2350; its share of
    the non-hash, non-NTT time is taken from the instruction profile, tools/mlkem_profile/profile.json)
Every result is serial (the host waits for the chip); docs in chipathon-2026 docs/tile_routes.md.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "model")]

import perf_model as PM  # noqa: E402
from config import PQM4  # noqa: E402

F_CHIP, F_RP = 50e6, 150e6
SETUP_S = 300 / F_RP
SW_CYC = {"ntt": 5992, "invntt": 5491, "basemul": 1613, "scale": 0}    # cited, ePrint 2022/112
NTT_CALLS = {"keygen": {"ntt": 4, "invntt": 0, "basemul": 4, "scale": 0},
             "encaps": {"ntt": 2, "invntt": 3, "basemul": 6, "scale": 3},
             "decaps": {"ntt": 4, "invntt": 4, "basemul": 8, "scale": 4}}

# hash calls, from the team's mlkem_model.py: (name, rate, bytes in, bytes out, secret input?)
SHA3_512, SHA3_256, SHAKE128, SHAKE256 = 72, 136, 168, 136
G = lambda n: ("G", SHA3_512, n, 64, True)
H_EK = ("H", SHA3_256, 800, 32, False)
J = ("J", SHAKE256, 800, 32, True)
XOF = ("XOF", SHAKE128, 34, 504, False)
PRF3 = ("PRF", SHAKE256, 33, 192, True)
PRF2 = ("PRF", SHAKE256, 33, 128, True)
CALLS = {"keygen": [G(33)] + [XOF] * 4 + [PRF3] * 4 + [H_EK],
         "encaps": [H_EK, G(64)] + [XOF] * 4 + [PRF3] * 2 + [PRF2] * 3,
         "decaps": [G(64), J] + [XOF] * 4 + [PRF3] * 2 + [PRF2] * 3}

# Keccak cores: (clocks per permutation, bits per I/O word K); measured by the team in RTL simulation
CORES = {"ring K=16": (172, 16), "ring K=8": (368, 8), "ring K=4": (760, 4), "ring K=2": (1544, 2),
         "latch": (1464, 8)}
FEED = {"as written": (23, 15), "optimized": (2, 2)}    # host CPU cycles per hash word in, per byte out


def perms(call):
    _, rate, n_in, n_out, _ = call
    return (n_in + 1 + rate - 1) // rate + (n_out + rate - 1) // rate - 1


def hash_words(call, K, burst=False):
    """(chip clocks of I/O, words the host builds, bytes it reads back) for one call, as in the team's
    chip_clocks(): K-bit words for K < 8, byte words for K >= 8 (the hash-only chip pairs bytes at K = 16)."""
    _, rate, n_in, n_out, _ = call
    steps, clear = 64 // min(K, 8), 64 // K
    full, rem = divmod(n_in + 1, rate)
    words = clear + full * rate * 8 // min(K, 8)                  # CLEAR + whole blocks
    if rem:
        data_lanes = (rem + 7) // 8
        words += data_lanes * steps + max(0, rate // 8 - data_lanes - 1) + steps
    out_lanes = (n_out + 7) // 8
    sq = out_lanes * steps                                        # squeeze clocks
    host = words + ((out_lanes * 8 + rate - 1) // rate if burst else sq)
    return words + sq, host, out_lanes * 8


def _cbd_share():
    """CBD's share of the time that is neither Keccak nor NTT, per operation (instruction profile)."""
    path = os.path.join(os.path.dirname(HERE), "tools", "mlkem_profile", "profile.json")
    out = {}
    for op, t in json.load(open(path))["table"].items():
        rest = sum(v for k, v in t.items() if not k.startswith(("SHA-3", "NTT")))
        out[op] = t["CBD sampling (SamplePolyCBD)"] / rest
    return out


def rp(op):
    cyc, share = PQM4[("ML-KEM-512", op)]
    total = cyc / F_RP
    return total, total * share


def hash_time(op, core, feed, which="all", burst=False):
    clk, K = CORES[core]
    total, hashing = rp(op)
    n_perm = sum(perms(c) for c in CALLS[op])
    per_sw = hashing / n_perm
    t = 0.0
    for c in CALLS[op]:
        if which == "all" or not c[4]:
            clocks, w, b = hash_words(c, K, burst)
            t += (clocks + perms(c) * clk) / F_CHIP + SETUP_S + (w * FEED[feed][0] + b * FEED[feed][1]) / F_RP
        else:
            t += perms(c) * per_sw
    return t


def ntt_time(op, where):
    calls = NTT_CALLS[op]
    if where == "software":
        return sum(n * SW_CYC[k] for k, n in calls.items()) / F_RP
    scen = {"chip, as written": "rp_fw", "chip, optimized": "pio_dma"}[where]
    return PM.chip_calls_s(calls, scenario=scen)


def exchange(core=None, feed="optimized", ntt="software", which="all", burst=False, cbd=False):
    t = 0.0
    share = _cbd_share() if cbd else {}
    for op in CALLS:
        total, hashing = rp(op)
        arith = sum(n * SW_CYC[k] for k, n in NTT_CALLS[op].items()) / F_RP
        rest = total - hashing - arith
        rest *= 1 - share.get(op, 0.0)
        t += rest + (hash_time(op, core, feed, which, burst) if core else hashing) + ntt_time(op, ntt)
    return t


def main():
    base = exchange()
    print(f"RP2350 alone: {base * 1e3:.2f} ms per ML-KEM-512 exchange\n")
    rows = [("RP2350 alone", None, "optimized", "software", "all"),
            ("NTT chip only (main), firmware as written", None, "optimized", "chip, as written", "all"),
            ("NTT chip only (main), optimized firmware", None, "optimized", "chip, optimized", "all")]
    for core in CORES:
        for feed in ("optimized", "as written"):
            rows.append((f"SHA-only {core}, feed {feed}", core, feed, "software", "all"))
        rows.append((f"SHA-only {core}, public inputs only, feed optimized", core, "optimized", "software", "public"))
    for core in ("ring K=8", "latch"):
        rows.append((f"NTT + {core}, all optimized", core, "optimized", "chip, optimized", "all"))
    for core in ("ring K=8", "ring K=16"):
        for feed in ("optimized", "as written"):
            rows.append((f"hash-only chip {core} + burst + CBD, feed {feed}", core, feed, "software", "all",
                         True, True))
    print(f"{'route':58} {'exchange':>9} {'vs RP2350':>9}")
    out = []
    for name, core, feed, ntt, which, *extra in rows:
        t = exchange(core, feed, ntt, which, *extra)
        out.append((name, t, base / t))
        print(f"{name:58} {t * 1e3:7.2f}ms {base / t:8.2f}x")
    return out


if __name__ == "__main__":
    main()
