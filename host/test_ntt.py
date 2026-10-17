"""Stage 5: replay the Stage-1 stimulus files on the Tang Nano running tt_um_ntt_engine and compare
every captured uo_out with the expected bytes (cycle-exact, same files the cocotb tests replay).

    make -C fpga prog            # bitstream with the NTT design from src/ (info.yaml)
    python host/test_ntt.py [--port P] [--div 1] [--files a a_shuffle]
    python host/test_ntt.py --mlkem ML-KEM-768        # full keygen + encaps + decaps on the board
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "model")]

from export import read  # noqa: E402
from host import Host  # noqa: E402
from chip_a import ChipA  # noqa: E402
from mlkem import PARAMS  # noqa: E402
from tt_emu import TTEmu  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--div", type=int, default=1, help="DUT clock = 13.5 MHz / div")
    ap.add_argument("--files", nargs="+", default=["a", "a_shuffle"])
    ap.add_argument("--mlkem", choices=list(PARAMS), help="replay a full ML-KEM keygen/encaps/decaps trace")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    emu = TTEmu(a.port, a.baud)
    print(f"{emu.port}: magic {emu.ping().decode()}")
    emu.set_div(a.div)
    ok = True
    runs = []
    if a.mlkem:
        import random
        rng = random.Random(a.seed)
        host = Host(ChipA(), record=True)
        kem, ref = PARAMS[a.mlkem](host), PARAMS[a.mlkem]()
        d, z, m = (rng.randbytes(32) for _ in range(3))
        ek, dk = kem.keygen_internal(d, z)
        K, c = kem.encaps_internal(ek, m)
        assert kem.decaps(dk, c) == K and (ek, dk) == ref.keygen_internal(d, z) and (K, c) == ref.encaps_internal(ek, m)
        print(f"{a.mlkem}: {len(host.stats)} chip calls, {len(host.trace.stim)} clocks; shared key {K.hex()[:16]}...")
        runs.append((a.mlkem, host.trace.stim, host.trace.expect))
    else:
        for name in a.files:
            runs.append((name, *read(os.path.join(ROOT, "test", "stimulus", f"{name}.txt"))))
    for name, stim, exp in runs:
        emu.set_inputs(0, 0)
        emu.reset(10)
        t = time.time()
        caps = emu.run_stream(stim)
        got = [c[0] for c in caps]
        bad = next((i for i, (g, e) in enumerate(zip(got, exp)) if g != e), None)
        if bad is None and all(c[1:] == (0, 0) for c in caps):
            print(f"{name}: {len(stim)} clocks, all uo_out bytes match ({time.time() - t:.1f} s)")
        else:
            ok = False
            print(f"{name}: FIRST MISMATCH at clock {bad}: got {got[bad]:#04x}, expected {exp[bad]:#04x}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
