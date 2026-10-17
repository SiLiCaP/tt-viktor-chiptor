"""Live demo of the NTT coprocessor running on the Tang Nano (or the Python model with --sim).

    python host/demo.py                 # board auto-detected
    python host/demo.py --sim           # rehearse without the board
    python host/demo.py --no-mlkem      # polynomial multiply only

All polynomial arithmetic runs on the chip: the PC sends one NTT layer at a time, reads the board's
results and builds the next layer from them. Writes slide figures (PNG) and a waveform (VCD) of the
real pins to reports/demo/.
"""
import argparse
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "sim"), os.path.join(ROOT, "model"), os.path.join(ROOT, "tools")]

from board import BoardBackend, SimEmu  # noqa: E402
from host import make_host  # noqa: E402
from mlkem import PARAMS  # noqa: E402

PS = "ML-KEM-512"           # parameter set (our target); --ps ML-KEM-768 to change
from mlkem_ntt_model import polymul_schoolbook  # noqa: E402
from protocol import LAT, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE  # noqa: E402

F_ASIC = 50e6
OK, FAIL = "\033[1;32mPASS\033[0m", "\033[1;31mFAIL\033[0m"

# chart tokens (dataviz reference palette, light surface)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def say(msg=""):
    print(msg, flush=True)


# ---------------------------------------------------------------- demos
def demo_polymul(be, rng):
    say("\n== 1. Polynomial multiply on the chip (team Spec 1 demo) ==")
    f = [rng.randrange(3329) for _ in range(256)]
    g = [rng.randrange(3329) for _ in range(256)]
    steps = [("forward NTT f", lambda s: be.ntt(f)), ("forward NTT g", lambda s: be.ntt(g)),
             ("basemul", lambda s: be.basemul(s["F"], s["G"])), ("inverse NTT", lambda s: be.invntt(s["H"])),
             ("scale", lambda s: be.scale(s["h"]))]
    s = {}
    for name, fn in steps:
        t = time.time()
        r = fn(s)
        key = {"forward NTT f": "F", "forward NTT g": "G", "basemul": "H", "inverse NTT": "h", "scale": "out"}[name]
        s[key] = r
        say(f"  chip: {name:14} done  ({time.time() - t:4.2f} s incl. USB)")
    t = time.time()
    ref = polymul_schoolbook(f, g)
    say(f"  CPU : schoolbook multiply mod X^256+1 ({time.time() - t:4.2f} s in Python)")
    match = sum(a == b for a, b in zip(s["out"], ref))
    say(f"  result: {match}/256 coefficients match  -> {OK if match == 256 else FAIL}")
    return f, g, s["out"], ref, match == 256


def demo_mlkem(be, rng, label):
    """ML-KEM with the chip, the same operations in pure Python, then the coefficients and predictions."""
    import perf_model as PM
    say(f"\n== 2. {PS} key exchange, every NTT/basemul on the chip ==")
    kem, ref = PARAMS[PS](backend=be), PARAMS[PS]()
    d, z, m = (rng.randbytes(32) for _ in range(3))
    meas = {}

    def run(op, fn, py_fn):
        be.reset_counters()
        t = time.perf_counter(); r = fn(); wall = time.perf_counter() - t
        t = time.perf_counter(); py_fn(); py = time.perf_counter() - t
        meas[op] = (wall, be.chip_s, dict(be.calls), py)
        return r

    ek, dk = run("keygen", lambda: kem.keygen_internal(d, z), lambda: ref.keygen_internal(d, z))
    say(f"  Alice: keygen      -> public key {len(ek)} B")
    K_bob, c = run("encaps", lambda: kem.encaps_internal(ek, m), lambda: ref.encaps_internal(ek, m))
    say(f"  Bob  : encapsulate -> ciphertext {len(c)} B, key {K_bob.hex()[:16]}...")
    K_alice = run("decaps", lambda: kem.decaps(dk, c), lambda: ref.decaps(dk, c))
    say(f"  Alice: decapsulate -> key {K_alice.hex()[:16]}...")
    same = K_alice == K_bob
    std = (ek, dk) == ref.keygen_internal(d, z) and (K_bob, c) == ref.encaps_internal(ek, m)
    say(f"  shared keys equal: {OK if same else FAIL}    identical to pure-software FIPS 203: {OK if std else FAIL}")

    say("\n== 3. An encrypted packet with the shared key ==")
    from packet import open_, seal
    msg = b"Meet at the chip fab at 9. Bring the GDS."
    blob = seal(K_bob, msg)
    got = open_(K_alice, blob)
    say(f"  Bob sends {len(blob)} B: {blob.hex()[:48]}...")
    say(f"  Alice reads: \u201c{got.decode()}\u201d  -> {OK if got == msg else FAIL}")
    bad = blob[:20] + bytes([blob[20] ^ 1]) + blob[21:]
    try:
        open_(K_alice, bad)
        tamper_ok = False
    except ValueError:
        tamper_ok = True
    say(f"  Eve flips one bit in transit -> Alice rejects it: {OK if tamper_ok else FAIL}")

    say("\n== 4. Performance: measured here -> predicted on the TT board ==")
    say(f"  {'op':7} {label:>26} {'Python only':>12} | {'K_py':>6} {'K_host':>7} {'K_chip':>9} | "
        f"{'RP2350 alone':>12} {'RP2350+chip':>12} {'vs alone':>8}")
    rows = {}
    for op, (wall, chip_s, calls, py) in meas.items():
        pr = PM.predict(op, py, wall - chip_s, chip_s, calls, ps=PS)
        c, P = pr["coefficients"], pr["predicted"]
        rows[op] = pr
        say(f"  {op:7} {wall:10.3f} s (chip {chip_s:6.3f} s) {py * 1e3:9.2f} ms | {c['K_py']:6.2f} {c['K_host']:7.2f} "
            f"{c['K_chip']:9.2e} | {P['rp2350_alone_s'] * 1e3:9.2f} ms {P['rp2350_plus_chip_s'] * 1e3:9.2f} ms "
            f"{P['speedup_vs_rp2350']:7.2f}x")
        try:
            import perf
            perf.append({"source": "demo", "kind": "measured", "backend": label, "op": op, "wall_s": wall,
                         "chip_s": chip_s, "host_s": wall - chip_s, "chip_calls": calls})
            perf.append({"source": "demo", "kind": "measured", "backend": "python-only (PC)", "op": op, "wall_s": py})
            perf.append({"source": "demo", "kind": "predicted", "backend": "RP2350 + our chip (TT board)", "op": op,
                         "corner": "nominal", "wall_s": P["rp2350_plus_chip_s"], "host_s": P["rp2350_host_s"],
                         "chip_s": P["chip_calls_s"], "coefficients": c, "chip_calls": calls})
            perf.append({"source": "demo", "kind": "predicted", "backend": "RP2350 alone (software)", "op": op,
                         "wall_s": P["rp2350_alone_s"], "coefficients": {"K_py": c["K_py"]}})
        except Exception as e:
            say(f"  (perf log not written: {e})")
    f, lim, _ = PM.f_chip()
    say(f"  RP2350 alone = Python-only x K_py; RP2350 + chip = host part x K_host + chip part x K_chip")
    say(f"  chip clock {f / 1e6:.0f} MHz (limited by {lim}); every input is listed in sim/config.py")
    return same and std and got == msg and tamper_ok


# ---------------------------------------------------------------- figures
def style(ax, title, subtitle=None):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=11)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=17, color=INK, fontweight="bold", pad=28 if subtitle else 12)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=12, color=INK2)


def fig_pin_timing(plt, first_batch, path, source, n=24):
    op, stim, uo = first_batch
    fig, ax = plt.subplots(figsize=(16, 6), facecolor=SURFACE)
    rows = [("valid", lambda w: (w >> 12) & 1), ("sof", lambda w: (w >> 13) & 1)]
    y = {"valid": 3.2, "sof": 2.4, "coeff in": 1.4, "uo_out": 0.3}
    for name, bit in rows:                                       # 1-bit lines
        xs, ys = [], []
        for i in range(n):
            v = bit(stim[i])
            xs += [i, i + 1]; ys += [y[name] + 0.5 * v] * 2
        ax.plot(xs, ys, color=SERIES[0], linewidth=2, solid_joinstyle="miter")
    for i in range(n):                                           # bus rows as labelled boxes
        w = stim[i]
        if (w >> 12) & 1:
            din = ((w >> 8) & 0xF) << 8 | (w & 0xFF)
            ax.add_patch(plt.Rectangle((i + 0.06, y["coeff in"]), 0.88, 0.6, color=SERIES[0], alpha=0.15, lw=0))
            ax.text(i + 0.5, y["coeff in"] + 0.3, str(din), ha="center", va="center", fontsize=9, color=INK)
        if uo[i]:
            ax.add_patch(plt.Rectangle((i + 0.06, y["uo_out"]), 0.88, 0.6, color=SERIES[1], alpha=0.18, lw=0))
            ax.text(i + 0.5, y["uo_out"] + 0.3, f"{uo[i]:02X}", ha="center", va="center", fontsize=10, color=INK)
    d = LAT[op]
    ax.annotate("", xy=(d, 1.12), xytext=(0, 1.12), arrowprops=dict(arrowstyle="->", color=INK2, lw=1.4))
    ax.text(d + 0.15, 1.12, f"D = {d} clocks: first input to first result byte", va="center", fontsize=11, color=INK2)
    ax.annotate("", xy=(3, 2.15), xytext=(0, 2.15), arrowprops=dict(arrowstyle="<->", color=INK2, lw=1.2))
    ax.text(3.2, 2.1, "3 clocks / butterfly", fontsize=10, color=INK2)
    ax.set_yticks([y[k] + 0.3 for k in y], list(y))
    ax.set_xticks(range(0, n + 1, 3))
    ax.set_xlim(0, n)
    ax.set_ylim(0, 4)
    ax.set_xlabel("clock", color=INK2, fontsize=12)
    style(ax, f"Chip pins, {source}: forward NTT, first butterflies",
          "Inputs b, a stream in; 3 result bytes (a', b' packed ByteEncode12) appear at a fixed delay, no handshake")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def fig_polymul(plt, chip, ref, path):
    fig, ax = plt.subplots(figsize=(16, 6), facecolor=SURFACE)
    xs = range(256)
    ax.plot(xs, ref, color=SERIES[0], linewidth=2, label="CPU schoolbook (reference)")
    ax.scatter(xs, chip, s=34, color=SERIES[1], edgecolors=SURFACE, linewidths=1.2, zorder=3,
               label="chip: NTT, NTT, basemul, INTT, scale")
    ax.set_xlim(-2, 258)
    ax.set_ylim(0, 3329)
    ax.set_xlabel("coefficient index", color=INK2, fontsize=12)
    ax.set_ylabel("value mod 3329", color=INK2, fontsize=12)
    match = sum(a == b for a, b in zip(chip, ref))
    style(ax, f"f × g mod (X²⁵⁶+1): chip result matches the CPU on {match}/256 coefficients",
          "two random polynomials; every dot (chip) sits on the line (reference)")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncols=2, frameon=False, fontsize=11, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def fig_clocks(plt, per_call, path):
    fig, ax = plt.subplots(figsize=(16, 6), facecolor=SURFACE)
    names = list(per_call)
    vals = [per_call[k] for k in names]
    bars = ax.barh(names, vals, height=0.5, color=SERIES[0], edgecolor=SURFACE, linewidth=2)
    for b, v in zip(bars, vals):
        ax.text(v + 30, b.get_y() + b.get_height() / 2, f"{v:,} clocks  =  {v / F_ASIC * 1e6:.0f} µs at 50 MHz",
                va="center", fontsize=12, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.5)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("chip clocks per call (one 256-coefficient polynomial)", color=INK2, fontsize=12)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    style(ax, "Chip time per operation",
          "1 butterfly / 3 clocks (pin-limited), 1 basemul piece / 15 clocks, verified cycle-exact on the FPGA")
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def fig_mlkem(plt, per_op, path):
    fig, ax = plt.subplots(figsize=(16, 6), facecolor=SURFACE)
    ops = list(per_op)
    modes = ["forward NTT", "basemul", "inverse NTT", "scale"]
    left = [0] * len(ops)
    for i, mode in enumerate(modes):
        vals = [per_op[o].get(mode, 0) for o in ops]
        ax.barh(ops, vals, left=left, height=0.5, color=SERIES[i], edgecolor=SURFACE, linewidth=2, label=mode)
        left = [a + b for a, b in zip(left, vals)]
    for y, tot in enumerate(left):
        ax.text(tot + 600, y, f"{tot:,} clocks  =  {tot / F_ASIC * 1e3:.2f} ms at 50 MHz", va="center",
                fontsize=12, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, max(left) * 1.45)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("chip clocks", color=INK2, fontsize=12)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), frameon=False, fontsize=11, ncols=4, labelcolor=INK2)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    style(ax, f"{PS}: chip work per operation",
          "hashing, sampling and encoding stay on the host; the chip does every NTT, basemul and scale")
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def write_vcd(first_batch, path):
    _, stim, uo = first_batch
    sig = {"clk": "!", "valid": '"', "sof": "#", "op": "$", "coeff": "%", "uo_out": "&"}
    lines = ["$timescale 10ns $end", "$scope module tt_um_ntt_engine_fpga $end",
             f"$var wire 1 {sig['clk']} clk $end", f"$var wire 1 {sig['valid']} valid $end",
             f"$var wire 1 {sig['sof']} sof $end", f"$var wire 2 {sig['op']} op $end",
             f"$var wire 12 {sig['coeff']} coeff $end", f"$var wire 8 {sig['uo_out']} uo_out $end",
             "$upscope $end", "$enddefinitions $end"]
    for i, (w, o) in enumerate(zip(stim, uo)):
        lines += [f"#{2 * i}", f"0{sig['clk']}", f"{(w >> 12) & 1}{sig['valid']}", f"{(w >> 13) & 1}{sig['sof']}",
                  f"b{(w >> 14) & 3:b} {sig['op']}", f"b{(((w >> 8) & 0xF) << 8) | (w & 0xFF):b} {sig['coeff']}",
                  f"b{o:b} {sig['uo_out']}", f"#{2 * i + 1}", f"1{sig['clk']}"]
    open(path, "w").write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="use the Python chip model instead of the board")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=1000000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--no-mlkem", action="store_true")
    ap.add_argument("--ps", default="ML-KEM-512", choices=["ML-KEM-512", "ML-KEM-768"], help="parameter set")
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "demo"))
    a = ap.parse_args()
    global PS
    PS = a.ps

    if a.sim:
        emu = SimEmu()
    else:
        from tt_emu import TTEmu
        emu = TTEmu(a.port, a.baud)
    say(f"connected: {emu.port} ({emu.ping().decode().strip()})")
    be = BoardBackend(emu, log_first=True)
    rng = random.Random(a.seed)

    f, g, chip, ref, ok1 = demo_polymul(be, rng)
    ok2 = demo_mlkem(be, rng, "chip model (PC)" if a.sim else "chip on FPGA (PC + Tang Nano)") if not a.no_mlkem else True

    # chip time as on the TT demo board (continuous streaming), from the cycle-accurate protocol model
    h = make_host("A")
    z = [0] * 256
    h.ntt(z); h.invntt(z); h.basemul(z, z); h.scale(z)
    per_call = dict(zip(["forward NTT", "inverse NTT", "basemul", "scale"], [s.clocks for s in h.stats]))
    names = {OP_CT: "forward NTT", OP_GS: "inverse NTT", OP_BASEMUL: "basemul", OP_SCALE: "scale"}
    counts = ({"keygen": {OP_CT: 4, OP_BASEMUL: 4}, "encaps": {OP_CT: 2, OP_BASEMUL: 6, OP_GS: 3, OP_SCALE: 3},
               "decaps": {OP_CT: 4, OP_BASEMUL: 8, OP_GS: 4, OP_SCALE: 4}} if PS == "ML-KEM-512" else
              {"keygen": {OP_CT: 6, OP_BASEMUL: 9}, "encaps": {OP_CT: 3, OP_BASEMUL: 12, OP_GS: 4, OP_SCALE: 4},
               "decaps": {OP_CT: 6, OP_BASEMUL: 15, OP_GS: 5, OP_SCALE: 5}})
    per_op = {o: {names[op]: n * per_call[names[op]] for op, n in c.items()} for o, c in counts.items()}

    os.makedirs(a.out, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.family"] = "DejaVu Sans"
        source = "simulated (Python chip model)" if a.sim else "captured from the FPGA"
        fig_pin_timing(plt, be.first_batch, os.path.join(a.out, "01_pin_timing.png"), source)
        fig_polymul(plt, chip, ref, os.path.join(a.out, "02_polymul.png"))
        fig_clocks(plt, per_call, os.path.join(a.out, "03_clocks_per_call.png"))
        fig_mlkem(plt, per_op, os.path.join(a.out, "04_mlkem_chip_work.png"))
    except ImportError:
        say("(matplotlib not installed: skipping figures)")
    write_vcd(be.first_batch, os.path.join(a.out, "pins_forward_ntt.vcd"))
    say(f"\nfigures + waveform written to {a.out}/  (open the .vcd with: surfer or gtkwave)")
    say(f"\nOVERALL: {OK if ok1 and ok2 else FAIL}")
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    sys.exit(main())
