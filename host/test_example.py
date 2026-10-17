"""Hardware bring-up test: the emulator running the template example logic (uo_out = ui_in + uio_in).

    python host/test_example.py [--port P] [--vectors 10000] [--div 1]

Step mode: SET_IN + STEP per vector. Run mode: LOAD/RUN/READ_CAP in 8192-word chunks, compared
cycle by cycle with host/dut_models.py, at every divider in --divs (fastest last).
"""
import argparse
import copy
import random
import sys
import time

from dut_models import MODELS, run_model
from tt_emu import TTEmu


def step_test(emu, model, n, rng):
    emu.set_inputs(0, 0)
    emu.reset(5)
    model.reset()
    for i in range(n):
        ui, uio = rng.randrange(256), rng.randrange(256)
        emu.set_inputs(ui, uio)
        model.cycle(ui, uio)
        got = emu.step(1)
        exp = copy.deepcopy(model).cycle(ui, uio)
        if got != exp:
            raise AssertionError(f"step vector {i}: ui={ui} uio={uio} got {got} expected {exp}")


def run_test(emu, model, n, div, rng):
    words = [rng.randrange(1 << 16) for _ in range(n)]
    emu.set_div(div)
    emu.reset(5)
    model.reset()
    caps = emu.run_stream(words)
    exp = run_model(model, words)
    for i, (g, e) in enumerate(zip(caps, exp)):
        if g != e:
            raise AssertionError(f"run div={div}: first mismatch at cycle {i}: got {g}, expected {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=1000000)
    ap.add_argument("--vectors", type=int, default=10000)
    ap.add_argument("--divs", default="8,4,2,1", help="run-mode dividers to test (DUT clock = 13.5 MHz / div)")
    ap.add_argument("--top", default="tt_um_emu_selftest", help="DUT model; tt_um_ntt_engine is tested with test_ntt.py")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    model = MODELS[a.top]()
    emu = TTEmu(a.port, a.baud)
    print(f"{emu.port}: magic {emu.ping().decode()}")

    t = time.time()
    step_test(emu, model, a.vectors, rng)
    print(f"step mode: {a.vectors} vectors OK ({time.time() - t:.1f} s)")

    for div in (int(d) for d in a.divs.split(",")):
        t = time.time()
        run_test(emu, model, a.vectors, div, rng)
        print(f"run mode div={div} (DUT {13.5 / div:.2f} MHz): {a.vectors} vectors OK ({time.time() - t:.1f} s)")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
