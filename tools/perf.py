"""Performance log, benchmark and plots for the presentation.

    python tools/perf.py bench            # Python-only vs chip-on-FPGA (if a board answers) + predictions
    python tools/perf.py bench --sim      # use the Python chip model instead of the board
    python tools/perf.py plot             # reports/perf/*.png from the whole log
    python tools/perf.py show             # print the log as a table

Every record is one JSON line in perf/perf_log.jsonl (append-only, committed), so the history of how fast
things got is kept. "kind" is "measured" or "predicted"; predictions carry their coefficients
(sim/perf_model.py explains them).
"""
import argparse
import datetime
import json
import os
import random
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, d) for d in ("host", "sim", "model")]
LOG = os.path.join(ROOT, "perf", "perf_log.jsonl")
OPS = ("keygen", "encaps", "decaps")

# ---------------------------------------------------------------- log


def git_rev():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True).stdout.strip() + ("+dirty" if subprocess.run(
                                  ["git", "-C", ROOT, "status", "--porcelain", "--untracked-files=no"],
                                  capture_output=True, text=True).stdout.strip() else "")
    except OSError:
        return "?"


def append(rec):
    rec = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "git": git_rev(), **rec}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def read_log():
    if not os.path.exists(LOG):
        return []
    return [json.loads(line) for line in open(LOG) if line.strip()]


# ---------------------------------------------------------------- benchmark


def run_kex(kem, rng_seed):
    """keygen, encaps, decaps of ML-KEM-768 -> {op: seconds}, shared key."""
    rng = random.Random(rng_seed)
    d, z, m = (rng.randbytes(32) for _ in range(3))
    t = {}
    t0 = time.perf_counter(); ek, dk = kem.keygen_internal(d, z); t["keygen"] = time.perf_counter() - t0
    t0 = time.perf_counter(); K, c = kem.encaps_internal(ek, m); t["encaps"] = time.perf_counter() - t0
    t0 = time.perf_counter(); K2 = kem.decaps(dk, c); t["decaps"] = time.perf_counter() - t0
    assert K == K2
    return t, K


def chip_run(be, seed):
    """Per-op measured wall, chip and host time with a BoardBackend, plus its chip calls."""
    from mlkem import MLKEM768
    kem = MLKEM768(backend=be)
    rng = random.Random(seed)
    d, z, m = (rng.randbytes(32) for _ in range(3))
    out = {}
    for op in OPS:
        be.reset_counters()
        t0 = time.perf_counter()
        if op == "keygen":
            ek, dk = kem.keygen_internal(d, z)
        elif op == "encaps":
            K, c = kem.encaps_internal(ek, m)
        else:
            assert kem.decaps(dk, c) == K
        wall = time.perf_counter() - t0
        out[op] = {"wall_s": wall, "chip_s": be.chip_s, "host_s": wall - be.chip_s, "calls": dict(be.calls)}
    return out


def bench(args):
    from board import BoardBackend, SimEmu
    from mlkem import MLKEM768
    import perf_model as PM

    seed = args.seed
    py = {op: [] for op in OPS}
    for _ in range(args.repeat):
        t, _ = run_kex(MLKEM768(), seed)
        for op in OPS:
            py[op].append(t[op])
    py = {op: statistics.median(v) for op, v in py.items()}
    for op in OPS:
        append({"source": "bench", "kind": "measured", "backend": "python-only (PC)", "op": op,
                "wall_s": py[op], "note": f"pure Python FIPS 203, median of {args.repeat}"})

    if args.sim:
        emu, label, baud = SimEmu(), "chip model (PC)", None
    else:
        from tt_emu import TTEmu
        emu, label, baud = TTEmu(args.port, args.baud), "chip on FPGA (PC + Tang Nano)", args.baud
    be = BoardBackend(emu)
    meas = chip_run(be, seed)
    rows = []
    for op in OPS:
        m = meas[op]
        append({"source": "bench", "kind": "measured", "backend": label, "op": op, "wall_s": m["wall_s"],
                "chip_s": m["chip_s"], "host_s": m["host_s"], "chip_calls": m["calls"], "uart_baud": baud,
                "note": "real coprocessor loop, one NTT layer per USB batch"})
        for corner in ("nominal", "slow"):
            pr = PM.predict(op, py[op], m["host_s"], m["chip_s"], m["calls"], corner)
            rec = append({"source": "bench", "kind": "predicted", "op": op, "corner": corner,
                          "backend": "RP2350 + our chip (TT board)", "wall_s": pr["predicted"]["rp2350_plus_chip_s"],
                          "host_s": pr["predicted"]["rp2350_host_s"], "chip_s": pr["predicted"]["chip_calls_s"],
                          "coefficients": pr["coefficients"], "f_chip_hz": pr["f_chip_hz"],
                          "f_chip_limited_by": pr["f_chip_limited_by"], "chip_calls": m["calls"],
                          "measured_from": label})
            if corner == "nominal":
                append({"source": "bench", "kind": "predicted", "op": op, "backend": "RP2350 alone (software)",
                        "wall_s": pr["predicted"]["rp2350_alone_s"],
                        "coefficients": {"K_py": pr["coefficients"]["K_py"]}, "note": "pqm4 m4fspeed cycles / 150 MHz"})
                rows.append((op, py[op], m, pr))
    print(f"\n{'op':7} {'Python-only':>12} {label:>30}   {'K_py':>9} {'K_host':>9} {'K_chip':>9}   "
          f"{'RP2350 alone':>13} {'RP2350+chip':>12} {'speedup':>8}")
    for op, p_, m, pr in rows:
        c = pr["coefficients"]
        print(f"{op:7} {p_:11.3f}s {m['wall_s']:9.3f}s (host {m['host_s']:.3f} + chip {m['chip_s']:.3f})   "
              f"{c['K_py']:9.2e} {c['K_host']:9.2e} {c['K_chip']:9.2e}   "
              f"{pr['predicted']['rp2350_alone_s'] * 1e3:10.2f} ms {pr['predicted']['rp2350_plus_chip_s'] * 1e3:9.2f} ms "
              f"{pr['predicted']['speedup_vs_rp2350']:7.2f}x")
    f, lim, _ = PM.f_chip("nominal")
    print(f"\nchip clock used for the prediction: {f / 1e6:.1f} MHz (limited by: {lim}); log: {LOG}")


# ---------------------------------------------------------------- backfill (numbers measured earlier today)

BACKFILL = [
    ("2026-10-17T16:00:00+03:00", "ceb87c7", "RTL simulation (cocotb/Icarus)", 7.46,
     "ML-KEM-768 keygen+encaps+decaps trace, 141,039 clocks, cycle-exact (test_mlkem768_through_rtl)"),
    ("2026-10-17T16:01:00+03:00", "0498779", "chip on FPGA, trace replay @115.2 kbaud", 61.5,
     "host/test_ntt.py --mlkem ML-KEM-768, 141,039 clocks, all bytes match"),
    ("2026-10-17T16:15:00+03:00", "0498779", "gate-level simulation (sky130 netlist)", 120.49,
     "same trace on the hardened netlist (GATES=yes)"),
    ("2026-10-17T16:19:00+03:00", "75070d0", "chip on FPGA, trace replay @1 Mbaud", 8.1,
     "same trace after raising the UART to 1 Mbaud"),
    ("2026-10-17T16:23:00+03:00", "75070d0", "chip on FPGA (PC + Tang Nano)", 11.2,
     "first live coprocessor loop (host/demo.py): keygen 2.7 s + encaps 3.5 s + decaps 5.0 s"),
]


def backfill(_args):
    have = {(r.get("ts"), r.get("backend")) for r in read_log()}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as fh:
        for ts, rev, backend, s, note in BACKFILL:
            if (ts, backend) in have:
                continue
            fh.write(json.dumps({"ts": ts, "git": rev, "source": "backfill (session log, time approximate)",
                                 "kind": "measured", "backend": backend, "op": "kex", "wall_s": s,
                                 "note": note}) + "\n")
    print(f"backfilled {len(BACKFILL)} early data points into {LOG}")


# ---------------------------------------------------------------- show / plot


def show(_args):
    for r in read_log():
        extra = f"  [{', '.join(f'{k}={v:.2e}' for k, v in r['coefficients'].items() if v)}]" if r.get("coefficients") else ""
        print(f"{r['ts'][:19]} {r['git']:>14} {r['kind']:9} {r['op']:6} {r['backend']:42} {r['wall_s']:10.4f} s"
              f"{' (' + r['corner'] + ')' if r.get('corner') else ''}{extra}")


SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def _style(ax, title, subtitle):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=11)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=17, color=INK, fontweight="bold", pad=28)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=12, color=INK2)


def _fmt_s(s):
    return f"{s:.1f} s" if s >= 1 else (f"{s * 1e3:.2f} ms" if s >= 1e-3 else f"{s * 1e6:.0f} µs")


def plot(_args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    out = os.path.join(ROOT, "reports", "perf")
    os.makedirs(out, exist_ok=True)
    log = read_log()

    # 1. journey: one ML-KEM-768 key exchange (keygen+encaps+decaps), each way we have run it
    kex = {}
    for r in log:
        if r.get("corner") == "slow":
            continue
        if r["op"] == "kex":
            kex.setdefault((r["kind"], r["backend"]), []).append((r["ts"], r["wall_s"]))
    sums = {}
    for r in log:
        if r["op"] in OPS and r.get("corner") != "slow":
            sums.setdefault((r["kind"], r["backend"], r["ts"][:16]), {})[r["op"]] = r["wall_s"]
    for (kind, backend, ts), v in sums.items():
        if len(v) == 3:
            kex.setdefault((kind, backend), []).append((ts, sum(v.values())))
    latest = sorted(((k, max(v)[1], min(v)[0]) for k, v in kex.items()), key=lambda x: x[2])
    fig, ax = plt.subplots(figsize=(16, 7), facecolor=SURFACE)
    labels = [f"{b}" + ("  (predicted)" if k == "predicted" else "") for (k, b), _, _ in latest]
    vals = [s for _, s, _ in latest]
    colors = [SERIES[1] if k == "predicted" else SERIES[0] for (k, _), _, _ in latest]
    bars = ax.barh(labels, vals, height=0.55, color=colors, edgecolor=SURFACE, linewidth=2)
    for b, v in zip(bars, vals):
        ax.text(v * 1.15, b.get_y() + b.get_height() / 2, _fmt_s(v), va="center", fontsize=12, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(min(vals) / 3, max(vals) * 12)
    ax.invert_yaxis()
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("seconds for one ML-KEM-768 key exchange (keygen + encaps + decaps), log scale", color=INK2, fontsize=12)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=SERIES[0], label="measured"), Patch(color=SERIES[1], label="predicted (sim/perf_model.py)")],
              loc="lower right", bbox_to_anchor=(1, 1.0), ncols=2, frameon=False, fontsize=11, labelcolor=INK2)
    _style(ax, "From simulation to silicon: one ML-KEM-768 key exchange",
           "oldest run at the top; latest value per setup; bars are wall-clock time")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "01_journey.png"), dpi=110, facecolor=SURFACE)
    plt.close(fig)

    # 2. latest bench: measured on the PC (s) and predicted on the TT board (ms), per operation
    bench = [r for r in log if r["source"] == "bench"]
    if bench:
        last_ts = max(r["ts"][:16] for r in bench)
        cur = [r for r in bench if r["ts"][:16] >= last_ts[:15]]
        latest_rec = {}
        for r in cur:
            if r.get("corner") == "slow":
                continue
            latest_rec[(r["kind"], r["backend"], r["op"])] = r
        fig, axes = plt.subplots(1, 2, figsize=(16, 6.5), facecolor=SURFACE)
        for ax, kind, unit, scale, title, sub in (
                (axes[0], "measured", "s", 1, "Measured today (PC)", "Python-only vs. Python host + our chip on the FPGA"),
                (axes[1], "predicted", "ms", 1e3, "Predicted on the TT demo board", "RP2350 alone vs. RP2350 + our chip")):
            keys = sorted({b for (k, b, o) in latest_rec if k == kind})
            x = range(len(OPS))
            w = 0.8 / max(len(keys), 1)
            for i, b in enumerate(keys):
                recs = [latest_rec.get((kind, b, op)) for op in OPS]
                host = [(r.get("host_s") or 0) * scale if r else 0 for r in recs]
                chip = [(r.get("chip_s") or 0) * scale if r else 0 for r in recs]
                tot = [(r["wall_s"] * scale) if r else 0 for r in recs]
                pos = [xi + (i - (len(keys) - 1) / 2) * w for xi in x]
                if any(chip):
                    ax.bar(pos, host, w, color=SERIES[i], edgecolor=SURFACE, linewidth=2, label=f"{b}: host part")
                    ax.bar(pos, chip, w, bottom=host, color=SERIES[i], alpha=0.45, edgecolor=SURFACE, linewidth=2,
                           label=f"{b}: chip calls", hatch="//")
                else:
                    ax.bar(pos, tot, w, color=SERIES[i], edgecolor=SURFACE, linewidth=2, label=b)
                for px, t in zip(pos, tot):
                    ax.text(px, t * 1.02, _fmt_s(t / scale), ha="center",
                            va="bottom", fontsize=10, color=INK)
            ax.set_xticks(list(x), list(OPS))
            ax.set_ylabel(unit, color=INK2, fontsize=12)
            ax.grid(axis="y", color=GRID, linewidth=0.8)
            ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK2)
            _style(ax, title, sub)
        fig.tight_layout()
        fig.savefig(os.path.join(out, "02_measured_vs_predicted.png"), dpi=110, facecolor=SURFACE)
        plt.close(fig)
    print(f"wrote {out}/01_journey.png and 02_measured_vs_predicted.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench")
    b.add_argument("--sim", action="store_true")
    b.add_argument("--port")
    b.add_argument("--baud", type=int, default=1000000)
    b.add_argument("--seed", type=int, default=2026)
    b.add_argument("--repeat", type=int, default=3)
    sub.add_parser("plot")
    sub.add_parser("show")
    sub.add_parser("backfill")
    a = ap.parse_args()
    {"bench": bench, "plot": plot, "show": show, "backfill": backfill}[a.cmd](a)


if __name__ == "__main__":
    main()
