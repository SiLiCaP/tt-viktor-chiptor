"""What could a 2x2 / 3x2 / 4x2 Tiny Tapeout chip do for ML-KEM?  Architecture exploration.

    python sim/arch_explore.py                  # ML-KEM-512 (our target)
    python sim/arch_explore.py ML-KEM-768

For each candidate design: synthesized (or estimated) cell area against the tile budget, and the
predicted time per ML-KEM operation on the TT demo board (RP2350 + chip), including moving every
bit over the pins. Every number is tagged: measured / cited / ESTIMATE.

Sources of the inputs:
  RP2350 software split (pqm4, cited): total cycles and hashing share per operation
  offloadable arithmetic (ePrint 2022/112 Table 2, cited): NTT 5,992, iNTT 5,491, basemul 1,613 cycles
  Keccak work per operation (measured by instrumenting model/mlkem.py, FIPS 203, 40 random seeds):
      ML-KEM-512 ~26-27 Keccak-f[1600] permutations, ~1.1-1.2 kB absorbed, ~2.7 kB squeezed
      ML-KEM-768 ~43-44 permutations, ~1.7-1.8 kB absorbed, ~5.1-5.2 kB squeezed
      (decaps without the optional dk check, which pqm4 does not do either)
  areas: our RTL and the team's tt_um_NTT_Core synthesized for sky130 (measured); Keccak-f 1 round/clock, a
      verified lane-serial Keccak-f (1,346 clocks) and a parallel K-RED multiplier synthesized for this
      exploration (measured, sim/arch_explore_rtl/); the clock-gated variant is an ESTIMATE
  tile budget: our 2x2 harden needed 1.6x the synthesized area once placed (measured); max ~70 % density
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "model")]

from config import PQM4  # noqa: E402

F_RP, F_CHIP = 150e6, 50e6
PS = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("ML-KEM") else "ML-KEM-512"
CALLS_BY_PS = {      # chip calls per operation (test/py/test_mlkem.py checks these)
    "ML-KEM-512": {"keygen": {"ntt": 4, "invntt": 0, "basemul": 4, "scale": 0},
                   "encaps": {"ntt": 2, "invntt": 3, "basemul": 6, "scale": 3},
                   "decaps": {"ntt": 4, "invntt": 4, "basemul": 8, "scale": 4}},
    "ML-KEM-768": {"keygen": {"ntt": 6, "invntt": 0, "basemul": 9, "scale": 0},
                   "encaps": {"ntt": 3, "invntt": 4, "basemul": 12, "scale": 4},
                   "decaps": {"ntt": 6, "invntt": 5, "basemul": 15, "scale": 5}}}
CALLS = CALLS_BY_PS[PS]
SW_CYC = {"ntt": 5992, "invntt": 5491, "basemul": 1613, "scale": 0}            # cited; scale is inside iNTT
# Keccak work per op, measured with the instrumented model (decaps: without the optional dk check)
KECCAK = {"ML-KEM-512": {"keygen": (27.0, 1101, 2749, 10), "encaps": (26.0, 1165, 2749, 11), "decaps": (26.0, 1165, 2749, 11)},
          "ML-KEM-768": {"keygen": (43.1, 1721, 5112, 17), "encaps": (44.1, 1785, 5240, 18), "decaps": (44.1, 1721, 5240, 18)}}[PS]
#            (permutations, bytes absorbed, bytes squeezed, hash calls)

# tile budget for synthesized area: core area x 70 % density / 1.6 (placed/synth, measured on our 2x2)
CORE_PER_TILE = 72565 / 4                                                      # measured, our 2x2 harden
BUDGET = {t: t * CORE_PER_TILE * 0.70 / 1.6 for t in (4, 6, 8)}

# chip blocks: (synthesized area um^2, tag)
AREA = {
    "ntt_A": (20042, "measured: our RTL, synthesized"),
    "ntt_A_par": (20042 - 7221 + 7022 + 600, "measured multiplier swap (+~600 control, ESTIMATE)"),
    "ntt_B3_par": (20042 + 16300, "ESTIMATE: handoff's block-engine extras (buffer + address gen + FSM)"),
    "keccak_round": (145288, "measured: Keccak-f[1600] 1 round/clock, synthesized"),
    "keccak_lane": (151452, "measured: sim/arch_explore_rtl/keccak_lane.v, verified, synthesized "
                            "(the 1,600 write-enabled state bits + 25:1 lane read mux dominate)"),
    "keccak_lane_cg": (110000, "ESTIMATE: keccak_lane with clock-gated registers instead of enable flip-flops"),
    "team_chip": (22903, "measured: chipathon-2026 tt_um_NTT_Core, synthesized"),
}
KECCAK_CLK = {"keccak_round": 24, "keccak_lane": 1346, "keccak_lane_cg": 1346}  # clocks/permutation (measured in RTL sim)

# NTT-engine time per call on the TT board, PIO+DMA (from sim/perf_model.py for A; others ESTIMATE)
NTT_CALL_US = {
    "team_chip": {"ntt": 75.0, "invntt": 75.0, "basemul": 42.1, "scale": 18.3},      # same protocol as ntt_A
    "ntt_A": {"ntt": 75.0, "invntt": 75.0, "basemul": 42.1, "scale": 18.3},          # model, CPU-bound feeding
    "ntt_A_par": {"ntt": 75.0, "invntt": 75.0, "basemul": 14.0, "scale": 9.0},       # basemul 5 clk/piece
    "ntt_B3_par": {"ntt": 25.0, "invntt": 25.0, "basemul": 14.0, "scale": 9.0},      # ~950 clk + gather/scatter
}
HASH_SETUP_CYC = 300                                                              # ASSUMPTION per hash call


def rp_split(op):
    cyc, share = PQM4[(PS, op)]
    total = cyc / F_RP
    hashing = cyc * share / F_RP
    arith = sum(n * SW_CYC[k] for k, n in CALLS[op].items()) / F_RP
    return total, hashing, arith, total - hashing - arith


def keccak_chip_s(op, core):
    perms, bin_, bout, calls = KECCAK[op]
    clocks = perms * KECCAK_CLK[core] + bin_ * 8 / 12 + bout                     # 12 input pins, 8 output pins
    return clocks / F_CHIP + calls * HASH_SETUP_CYC / F_RP


def option_time(op, ntt=None, keccak=None):
    total, hashing, arith, rest = rp_split(op)
    h = keccak_chip_s(op, keccak) if keccak else hashing
    a = sum(n * NTT_CALL_US[ntt][k] * 1e-6 for k, n in CALLS[op].items()) if ntt else arith
    return rest + h + a, {"rest": rest, "hashing": h, "arith": a}


OPTIONS = [
    ("RP2350 alone (software)", None, None),
    ("today: NTT engine A", "ntt_A", None),
    ("A + parallel multiplier (same area)", "ntt_A_par", None),
    ("NTT block engine B3 + parallel mult.", "ntt_B3_par", None),
    ("Keccak lane-serial (measured RTL)", None, "keccak_lane"),
    ("Keccak lane-serial, clock-gated (est.)", None, "keccak_lane_cg"),
    ("Keccak lane-serial + team NTT chip", "team_chip", "keccak_lane"),
    ("Keccak 1 round/clock (SW arithmetic)", None, "keccak_round"),
    ("Keccak 1 round/clock + NTT B3", "ntt_B3_par", "keccak_round"),
]


def area_of(ntt, keccak):
    return (AREA[ntt][0] if ntt else 0) + (AREA[keccak][0] if keccak else 0)


def fits(a):
    for t, name in ((4, "2x2"), (6, "3x2"), (8, "4x2")):
        if a <= BUDGET[t]:
            return name
    return f"no ({a / (CORE_PER_TILE * 0.70 / 1.6):.0f} tiles)"


def main():
    print(f"RP2350 alone, {PS} (pqm4 m4fspeed cycles at 150 MHz):")
    for op in CALLS:
        t, h, a, r = rp_split(op)
        print(f"  {op:7} {t * 1e3:5.2f} ms = hashing {h * 1e3:4.2f} ({h / t:4.0%}) + NTT/basemul {a * 1e3:4.2f} ({a / t:3.0%}) "
              f"+ rest {r * 1e3:4.2f} ({r / t:3.0%})  -> ceilings: NTT unit {t / (t - a):4.2f}x, Keccak unit {t / (t - h):4.2f}x, "
              f"both {t / r:4.2f}x")
    print(f"\ntile budget for synthesized logic (ESTIMATE): " + ", ".join(f"{n} {BUDGET[t] / 1e3:.0f}k um^2"
                                                                     for t, n in ((4, "2x2"), (6, "3x2"), (8, "4x2"))))
    print(f"\n{'option':42} {'area':>9} {'fits':>14} | {'keygen':>8} {'encaps':>8} {'decaps':>8} | speedup")
    rows = []
    for name, ntt, kec in OPTIONS:
        a = area_of(ntt, kec)
        ts = {op: option_time(op, ntt, kec)[0] for op in CALLS}
        base = {op: rp_split(op)[0] for op in CALLS}
        sp = sum(base.values()) / sum(ts.values())
        rows.append((name, a, ts, sp))
        print(f"{name:42} {a / 1e3:7.0f}k {fits(a) if a else '-':>14} | " +
              " ".join(f"{ts[op] * 1e3:6.2f}ms" for op in CALLS) + f" | {sp:5.2f}x")
    return rows


def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
    fig, ax = plt.subplots(figsize=(17, 7.5), facecolor=SURFACE)
    names = []
    for i, (name, ntt, kec) in enumerate(OPTIONS):
        parts = {"rest": 0, "hashing": 0, "arith": 0}
        for op in CALLS:
            for k, v in option_time(op, ntt, kec)[1].items():
                parts[k] += v * 1e3
        left = 0
        for j, (k, lbl) in enumerate((("hashing", "SHA-3 / SHAKE (Keccak)"), ("arith", "NTT / basemul / scale"),
                                      ("rest", "everything else (sampling, encoding, ...)"))):
            ax.barh(i, parts[k], left=left, height=0.6, color=SERIES[j], edgecolor=SURFACE, linewidth=2,
                    label=lbl if i == 0 else None)
            left += parts[k]
        a = area_of(ntt, kec)
        fit = fits(a) if a else "no chip"
        ax.text(left + 0.15, i, f"{left:.1f} ms   {rows[i][3]:.2f}x   [{fit}]", va="center", fontsize=11,
                color=INK if (not a or not fit.startswith("no")) else INK2)
        names.append(name)
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlim(0, max(sum(option_time(op, n, k)[0] for op in CALLS) for _, n, k in OPTIONS) * 1e3 * 1.45)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(colors=INK2, labelsize=11)
    ax.set_xlabel(f"ms for one {PS} key exchange (keygen + encaps + decaps) on the TT board, transfers included",
                  color=INK2, fontsize=12)
    ax.set_title(f"What could our chip do? {PS}: time per key exchange by design", loc="left", fontsize=17, color=INK,
                 fontweight="bold", pad=30)
    ax.text(0, 1.02, "[fits in] = smallest tile combo whose cell budget it fits (estimate); hashing is ~3/4 of ML-KEM",
            transform=ax.transAxes, fontsize=12, color=INK2)
    ax.legend(loc="lower right", frameon=False, fontsize=11, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(HERE), "reports", "perf",
                       "05_architecture_options.png" if PS == "ML-KEM-512" else f"05_architecture_options_{PS[-3:]}.png")
    plot(main(), out)
    print(f"\nwrote {out}")
