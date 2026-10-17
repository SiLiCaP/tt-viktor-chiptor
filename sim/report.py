"""I/O bottleneck report (handoff section 6): writes reports/bottleneck.md and reports/bottleneck.csv.

    python sim/report.py

Per-call clocks and pin traffic come from the cycle-accurate models (sim/). Every host-side number
comes from sim/config.py and is labelled there as cited or ASSUMPTION.
"""
import csv
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "model")]

from config import F_CHIP_SWEEP_HZ, PARAMS, PQM4, SOURCES, p  # noqa: E402
from host import make_host  # noqa: E402
from mlkem import PARAMS as KEMS, CountingBackend, ReferenceBackend  # noqa: E402

DESIGNS = {"A": "A", "B1": "B"}          # A = team design (Spec 1-5); B1 = experimental block engine
OPS = ("keygen", "encaps", "decaps")
MODES = ("ideal_pio", "pio_fifo_cpu", "bitbang")


def call_profiles():
    """design -> backend op -> dict(clocks, words, bytes, units, unit_kind) from the simulator."""
    rng = random.Random(0)
    f = [rng.randrange(3329) for _ in range(256)]
    prof = {}
    for name, design in DESIGNS.items():
        h = make_host(design)
        h.ntt(f); h.invntt(f); h.scale(f); h.basemul(f, f)
        prof[name] = {}
        for s in h.stats:
            if s.op in ("ntt", "invntt"):
                units, kind = (896, "butterfly") if design == "A" else (32, "block")
            else:
                units, kind = 128, "transaction"
            prof[name][s.op] = dict(clocks=s.clocks, words=s.words_in, bytes=s.bytes_out,
                                    units=units, kind=kind, source="simulated")
    b3 = {op: dict(v) for op, v in prof["B1"].items()}          # B3: handoff estimate, not built
    for op in ("ntt", "invntt"):
        b3[op].update(clocks=p("b3_ntt_clocks"), source="ASSUMPTION")
    prof["B3"] = b3
    return prof


def call_counts():
    rng = random.Random(1)
    counts = {}
    for ps in ("ML-KEM-512", "ML-KEM-768"):
        be = CountingBackend(ReferenceBackend())
        kem = KEMS[ps](be)
        for op in OPS:
            if op == "keygen":
                ek, dk = kem.keygen_internal(rng.randbytes(32), rng.randbytes(32))
            elif op == "encaps":
                K, c = kem.encaps_internal(ek, rng.randbytes(32))
            else:
                kem.decaps(dk, c)
            counts[(ps, op)] = dict(be.counts)
            be.counts = dict.fromkeys(be.counts, 0)
    return counts


def call_time(prof, f_chip, mode):
    """-> dict of seconds for one chip call."""
    f_rp = p("f_rp_hz")
    f_eff = min(f_chip, f_rp / p("pio_cycles_per_chip_clock"))
    if mode == "bitbang":
        f_eff = min(f_chip, f_rp / p("bitbang_cycles_per_clock"))
    stream = prof["clocks"] / f_eff
    pin_clocks = min(max(prof["words"], prof["bytes"]), prof["clocks"])
    xfer = 0.0
    if mode == "pio_fifo_cpu":   # no back-pressure: the chip clock must slow down to what the CPU sustains
        xfer = (prof["words"] * p("fifo_cpu_cycles_per_word") + prof["bytes"] * p("fifo_cpu_cycles_per_byte")) / f_rp
    io = max(stream, xfer)
    per_unit = p("book_per_block") if prof["kind"] == "block" else (
        p("book_per_butterfly") if prof["kind"] == "butterfly" else p("book_per_transaction"))
    book = prof["units"] * per_unit / f_rp * (1 - p("book_overlap"))
    return dict(pins=pin_clocks / f_eff, compute=(prof["clocks"] - pin_clocks) / f_eff,
                host_xfer=io - stream, host_book=book, total=io + book)


def evaluate(profiles, counts):
    rows = []
    f_rp = p("f_rp_hz")
    for ps in ("ML-KEM-512", "ML-KEM-768"):
        for op in OPS:
            sw_cycles, hash_share = PQM4[(ps, op)]
            sw_cycles *= p("m33_vs_m4")
            c = counts[(ps, op)]
            offloaded = c["ntt"] * p("sw_ntt") + c["invntt"] * p("sw_invntt") + c["basemul"] * p("sw_basemul")
            rest = (sw_cycles - offloaded * p("m33_vs_m4")) / f_rp       # host work the chip never touches
            for design, prof in profiles.items():
                for f_chip in F_CHIP_SWEEP_HZ[0]:
                    for mode in MODES:
                        acc = dict(pins=0.0, compute=0.0, host_xfer=0.0, host_book=0.0, chip_calls=0.0)
                        for bop, n in counts[(ps, op)].items():
                            t = call_time(prof[bop], f_chip, mode)
                            for k in ("pins", "compute", "host_xfer", "host_book"):
                                acc[k] += n * t[k]
                            acc["chip_calls"] += n * t["total"]
                        parts = {"pin transfer": acc["pins"], "chip compute": acc["compute"],
                                 "host transfer": acc["host_xfer"], "host bookkeeping": acc["host_book"]}
                        total = rest + acc["chip_calls"]
                        rows.append(dict(
                            paramset=ps, op=op, design=design, f_chip_mhz=f_chip / 1e6, mode=mode,
                            total_us=total * 1e6, pins_us=acc["pins"] * 1e6, compute_us=acc["compute"] * 1e6,
                            host_xfer_us=acc["host_xfer"] * 1e6, host_book_us=acc["host_book"] * 1e6,
                            host_rest_us=rest * 1e6, sw_baseline_us=sw_cycles / f_rp * 1e6,
                            speedup=sw_cycles / f_rp / total,
                            chip_bottleneck=max(parts, key=parts.get),
                            overall_bottleneck="host (hashing etc.)" if rest > acc["chip_calls"] else "coprocessor path"))
    return rows


def write(profiles, counts, rows, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "bottleneck.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    L = ["# I/O bottleneck report", "",
         "Generated by `python sim/report.py`. Chip clocks and pin traffic are **simulated** (cycle-accurate",
         "models, latencies from `docs/PROTOCOL.md`, still PROPOSED). Host numbers are **assumptions** from",
         "`sim/config.py` unless marked cited. Times in µs.", "",
         "## Per chip call (one polynomial)", "",
         "| design | op | clocks | words in | bytes out | source |", "|---|---|---|---|---|---|"]
    for d, prof in profiles.items():
        for op, v in prof.items():
            L.append(f"| {d} | {op} | {v['clocks']:,} | {v['words']:,} | {v['bytes']:,} | {v['source']} |")
    L += ["", "## Chip calls per ML-KEM operation (from model/mlkem.py)", "",
          "| param set | op | NTT | INTT | scale | basemul |", "|---|---|---|---|---|---|"]
    for (ps, op), c in counts.items():
        L.append(f"| {ps} | {op} | {c['ntt']} | {c['invntt']} | {c['scale']} | {c['basemul']} |")

    def table(sel, title):
        L.extend(["", f"## {title}", "",
                  "| param set | op | design | total | pins | chip compute | host xfer | host book | host rest | SW baseline | speedup | coprocessor bottleneck |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"])
        for r in rows:
            if sel(r):
                L.append(f"| {r['paramset']} | {r['op']} | {r['design']} | {r['total_us']:,.0f} | {r['pins_us']:,.0f} | "
                         f"{r['compute_us']:,.0f} | {r['host_xfer_us']:,.0f} | {r['host_book_us']:,.0f} | {r['host_rest_us']:,.0f} | "
                         f"{r['sw_baseline_us']:,.0f} | {r['speedup']:.2f}× | {r['chip_bottleneck']} |")

    for f in F_CHIP_SWEEP_HZ[0]:
        table(lambda r, f=f: r["mode"] == "ideal_pio" and r["f_chip_mhz"] == f / 1e6,
              f"Ideal PIO lockstep, f_chip = {f / 1e6:.0f} MHz")
    table(lambda r: r["mode"] == "pio_fifo_cpu" and r["f_chip_mhz"] == 50, "PIO + FIFO + CPU refill, f_chip = 50 MHz")
    table(lambda r: r["mode"] == "bitbang" and r["f_chip_mhz"] == 50, "Bit-banged GPIO, f_chip = 50 MHz (CPU-limited)")

    L += ["", "## Parameters", "", "| name | value | status |", "|---|---|---|",
          f"| f_chip sweep | {', '.join(f'{f / 1e6:.0f} MHz' for f in F_CHIP_SWEEP_HZ[0])} | {F_CHIP_SWEEP_HZ[1]} |"]
    for k, (v, s) in PARAMS.items():
        L.append(f"| {k} | {v:g} | {s} |")
    L += ["", "## Sources", ""] + [f"- **{k}**: {v}" for k, v in SOURCES.items()]
    L += ["", "Host work the chip never touches = pqm4 total minus the cited software cost of the offloaded",
          "calls (ePrint 2022/112 Table 2). The pqm4 hashing share shows where that time goes:"]
    for (ps, op), (cyc, hs) in PQM4.items():
        L.append(f"- {ps} {op}: {cyc:,} cycles, {hs:.1%} hashing")
    with open(os.path.join(outdir, "bottleneck.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")


def main():
    profiles, counts = call_profiles(), call_counts()
    rows = evaluate(profiles, counts)
    out = os.path.join(ROOT, "reports")
    write(profiles, counts, rows, out)
    print(f"wrote {out}/bottleneck.md and bottleneck.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
