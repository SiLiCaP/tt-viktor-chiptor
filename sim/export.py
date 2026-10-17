"""Stage-1 stimulus export: per-clock pin stimulus + expected uo_out, replayed by cocotb (test/) and
the Tang Nano player (host/). Every file starts right after reset is released.

    python sim/export.py [outdir]          # default test/stimulus/

File format (text, one clock per line, '#' lines are comments):
    SSSS EE      SSSS = 16-bit {uio_in, ui_in} hex, EE = expected uo_out hex
Comment lines carry the variant, seed and the clock at which each call starts (# call <clock> <op>).
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "model")]

from host import make_host  # noqa: E402

VARIANTS = {"a": ("A", False), "a_shuffle": ("A", True),          # a = the team design (Spec 1-5)
            "b": ("B", False), "b_shuffle": ("B", True)}           # b = experimental block engine


def generate(variant, seed=1):
    """-> Trace with ntt, invntt, scale, basemul of random polynomials, back to back."""
    design, shuffle = VARIANTS[variant]
    rng = random.Random(seed)
    f = [rng.randrange(3329) for _ in range(256)]
    g = [rng.randrange(3329) for _ in range(256)]
    h = make_host(design, shuffle, record=True, seed=seed)
    h.ntt(f); h.invntt(f); h.scale(f); h.basemul(f, g)
    return h.trace


def write(path, trace, header=""):
    marks = dict(trace.marks)
    with open(path, "w") as fh:
        fh.write(f"# {header}\n")
        for i, (s, e) in enumerate(zip(trace.stim, trace.expect)):
            if i in marks:
                fh.write(f"# call {i} {marks[i]}\n")
            fh.write(f"{s:04x} {e:02x}\n")


def read(path):
    """-> (stim words, expected uo_out)"""
    stim, exp = [], []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        s, e = line.split()
        stim.append(int(s, 16)); exp.append(int(e, 16))
    return stim, exp


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "test", "stimulus")
    os.makedirs(out, exist_ok=True)
    for v in VARIANTS:
        t = generate(v)
        write(os.path.join(out, f"{v}.txt"), t, f"variant {v} seed 1: ntt, invntt, scale, basemul")
        print(f"{v}: {len(t.stim)} clocks")


if __name__ == "__main__":
    main()
