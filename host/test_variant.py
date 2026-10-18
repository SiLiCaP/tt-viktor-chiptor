"""Run a chip variant's own functions on the FPGA, over USB (Tang Nano alone) or through the Pico 2 W rig:
hash jobs for a Keccak core at its width K, and/or the ML-KEM-512 NTT check for an NTT core.

    make -C fpga prog GL=0 DESIGN_ROOT=~/tools/work/exp/sha_k8_2x2 BUILD_TAG=_sha_k8 \\
         CHPARAM='chparam -set CLOCK_GATING 0 keccak_ring;'          (add TARGET=pico for the rig)
    python3 host/test_variant.py --port /dev/ttyUSB2 --hash 8              # Tang Nano USB
    python3 host/test_variant.py --port /dev/ttyACM0 --hash 8 --ntt        # the rig, NTT + hash chip
    python3 host/test_variant.py --port /dev/ttyACM0 --hash 8 --hash-only  # the hash-only chip (sha3-only):
                                                                            # + bursts and SamplePolyCBD

Every digest is compared with hashlib; NTT results with the cycle model (host/test_ntt.py --mlkem).
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hash_jobs import hash_only_jobs, standard_jobs  # noqa: E402
from tt_emu import TTEmu  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True)
    ap.add_argument("--hash", type=int, choices=[2, 4, 8, 16], help="Keccak core width K")
    ap.add_argument("--core", default="ring", choices=["ring", "lat"])
    ap.add_argument("--hash-only", action="store_true", help="also the hash-only chip's BURST and BURST_CBD jobs")
    ap.add_argument("--ntt", action="store_true", help="also run the ML-KEM-512 NTT check")
    a = ap.parse_args()
    ok = True
    if a.hash:
        emu = TTEmu(a.port)
        print(f"{a.port}: magic {emu.ping().decode()}")
        emu.set_inputs(0, 0)
        emu.reset(10)
        t = time.time()
        jobs = standard_jobs(a.hash, a.core) + (hash_only_jobs(a.hash) if a.hash_only else [])
        clocks = quiet = 0
        for job in jobs:
            words, sq = job.words()
            samples = [c[0] for c in emu.run_stream(words)]
            clocks += len(words)
            got = job.digest(samples, sq)
            due = {k + 2 for k in sq}
            quiet += sum(1 for k, s in enumerate(samples) if k not in due and s)
            kind = f"cbd eta={job.cbd_eta}" if job.cbd_eta else ("burst" if job.burst else "bytes")
            if got != job.expected():
                show = (lambda v: bytes(x & 0xFF for x in v).hex()[:24]) if job.cbd_eta else (lambda v: v.hex()[:24])
                print(f"  FAIL {job.name} {kind} len {len(job.msg)}: {show(got)} != {show(job.expected())}")
                ok = False
        if a.hash_only and quiet:
            print(f"  uo_out nonzero on {quiet} samples where no byte was due")
            ok = False
        print(f"hash, {a.core} K={a.hash}: {len(jobs)} jobs, {clocks} clocks, "
              f"{'every output equals hashlib / SamplePolyCBD' if ok else 'MISMATCH'} ({time.time() - t:.1f} s)")
        emu.close()
    if a.ntt:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_ntt.py"), "--port", a.port, "--seeds", "1"])
        ok &= r.returncode == 0
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
