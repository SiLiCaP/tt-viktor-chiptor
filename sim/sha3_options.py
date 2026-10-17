"""SHA-3 / SHAKE in ML-KEM-512: where the time goes and what each speed-up option buys.

    python sim/sha3_options.py [out.png]

Inputs (same as sim/arch_explore.py):
  RP2350 time and hashing share per operation: pqm4 m4fspeed cycles at 150 MHz (cited, sim/config.py)
  Keccak-f[1600] permutations per hash call: measured by instrumenting model/mlkem.py (FIPS 203)
  on-chip Keccak: keccak_lane_lat.v, 1,346 clocks per permutation at 50 MHz, 99k um^2 (measured)
Software options (A-hat reuse, dual-core hashing) are ESTIMATES: permutations removed or halved at the
measured average cost per permutation, no synchronization overhead.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "model")]
sys.argv = sys.argv[:1] + [a for a in sys.argv[1:] if not a.startswith("ML-KEM")]

import arch_explore as A  # noqa: E402

# Keccak-f[1600] permutations per hash function, ML-KEM-512 (decaps without the optional dk check)
PERMS = {"keygen": {"G": 1, "H": 6, "PRF": 8, "XOF": 12},
         "encaps": {"G": 1, "H": 6, "PRF": 7, "XOF": 12},
         "decaps": {"G": 1, "J": 6, "PRF": 7, "XOF": 12}}
SECRET_INPUT = {"G", "PRF", "J"}            # d, sigma, m, r, z: secret; rho (XOF) and ek (H): public
OPS = list(PERMS)


def per_op():
    rows = {}
    for op in OPS:
        t, h, _, _ = A.rp_split(op)
        n = sum(PERMS[op].values())
        per = h / n                                                     # s per permutation, incl. absorb/squeeze
        pub = sum(v for k, v in PERMS[op].items() if k not in SECRET_INPUT)
        chip = A.keccak_chip_s(op, "keccak_lane_lat")                   # all hashing on chip, pins included
        reuse = {"keygen": 0, "encaps": 0, "decaps": PERMS[op]["XOF"]}[op]   # A-hat kept from keygen
        par = PERMS[op]["XOF"] - reuse + PERMS[op]["PRF"]                    # independent calls, split 2 cores
        rows[op] = {
            "rp2350": t,
            "reuse": t - reuse * per,
            "reuse_dual": t - reuse * per - par / 2 * per,
            "hw_public": t - pub * per + chip * pub / n,
            "hw_all": t - h + chip,
            "_hash": h, "_perms": n, "_per": per, "_public": pub,
        }
    return rows


OPTIONS = [  # key, label, kind
    ("rp2350", "RP2350 alone (software)", "base"),
    ("ntt_chip", "+ our NTT chip, optimized firmware (4 tiles)", "ntt"),
    ("reuse", "software: keep A-hat from keygen for decaps", "sw"),
    ("reuse_dual", "software: + hash on both M33 cores", "sw"),
    ("hw_public", "Keccak on chip, public inputs only (~13 tiles)", "hw"),
    ("hw_all", "Keccak on chip, all hashing (~13 tiles)", "hw"),
    ("hw_round", "Keccak 1 round/clock on chip (~18 tiles)", "hw"),
]


def exchange_totals(rows):
    tot = {k: sum(rows[op][k] for op in OPS) for k in ("rp2350", "reuse", "reuse_dual", "hw_public", "hw_all")}
    tot["ntt_chip"] = sum(A.option_time(op, "team_chip", None)[0] for op in OPS)
    tot["hw_round"] = sum(A.option_time(op, None, "keccak_round")[0] for op in OPS)
    return tot


def main():
    rows = per_op()
    print("ML-KEM-512 on the RP2350 alone:")
    for op in OPS:
        r = rows[op]
        print(f"  {op:7} {r['rp2350'] * 1e3:.2f} ms, hashing {r['_hash'] * 1e3:.2f} ms ({r['_hash'] / r['rp2350']:.0%}), "
              f"{r['_perms']} permutations, {r['_per'] * 1e6:.1f} us each, {r['_public']} with public inputs")
    print(f"\n{'option':48} {'keygen':>8} {'encaps':>8} {'decaps':>8} {'exchange':>9}")
    tot = exchange_totals(rows)
    for key, label, _ in OPTIONS:
        if key in rows[OPS[0]]:
            cells = " ".join(f"{rows[op][key] * 1e3:6.2f}ms" for op in OPS)
        else:
            cells = " " * 26
        print(f"{label:48} {cells} {tot[key] * 1e3:6.2f}ms {tot['rp2350'] / tot[key]:5.2f}x")
    return tot


def plot(tot, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    COL = {"base": "#8a8f9c", "ntt": "#eb6834", "sw": "#1baf7a", "hw": "#2a78d6"}
    fig, ax = plt.subplots(figsize=(15, 6.2), facecolor=SURFACE)
    base = tot["rp2350"]
    for i, (key, label, kind) in enumerate(OPTIONS):
        v = tot[key] * 1e3
        ax.barh(i, v, height=0.62, color=COL[kind], hatch="//" if kind == "hw" else None,
                edgecolor=SURFACE if kind != "hw" else "#cfe0f5", linewidth=0)
        ax.text(v + 0.1, i, f"{v:.2f} ms   {base / tot[key]:.2f}x", va="center", fontsize=12, color=INK)
    ax.set_yticks(range(len(OPTIONS)), [o[1] for o in OPTIONS])
    ax.invert_yaxis()
    ax.set_xlim(0, base * 1e3 * 1.45)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(colors=INK2, labelsize=12)
    ax.set_xlabel("ms for one ML-KEM-512 key exchange (keygen + encaps + decaps), fresh keys", color=INK2, fontsize=12)
    ax.set_title("SHA-3 decides ML-KEM's speed", loc="left", fontsize=17, color=INK, fontweight="bold", pad=28)
    ax.text(0, 1.02, "grey: software today · orange: our NTT chip · green: software only (estimate) · "
            "blue, hatched: Keccak hardware, too big for 8 tiles", transform=ax.transAxes, fontsize=10.5, color=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    t = main()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "reports", "perf", "06_sha3_options.png")
    plot(t, out)
    print(f"\nwrote {out}")
