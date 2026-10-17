"""The team chip's arithmetic (NTT_CHIP=team, 3 K-RED rounds) against the team's own reference model,
chipathon-2026/test/ntt_ref.py, when that repo is checked out next to this one."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEAM_TEST = os.path.join(os.path.dirname(ROOT), "chipathon-2026", "test")

CHECK = r"""
import random, sys
sys.path[:0] = [{model!r}, {sim!r}, {team!r}]
import chip_arith as C, ntt_ref as R
assert (C.CHIP, C.FACTOR, C.INV_FACTOR, C.SCALE_C if hasattr(C, 'SCALE_C') else C.SCALE_CONST) == ('team', R.KM, R.KM_INV, R.SCALE_C)
assert C.ROM_P == R.ZETA_S and [C.gamma_p(i) for i in range(128)] == R.GAMMA_S
for a in range(0, 3329, 7):
    for b in range(0, 3329, 13):
        assert C.mul(a, b) == R.chip_mul(a, b)
rng = random.Random(3)
for _ in range(200):
    f0, f1, g0, g1 = (rng.randrange(3329) for _ in range(4)); i = rng.randrange(128)
    assert C.basemul_piece(f0, f1, g0, g1, i) == R.chip_basemul_piece(f0, f1, g0, g1, R.GAMMA_S[i])
    c = rng.randrange(3329); assert C.scale(c) == R.chip_scale([c])[0]
# whole flow on the cycle model of the pins, then compare with schoolbook
from chip_a import ChipA
from host import Host
h = Host(ChipA())
f = [rng.randrange(3329) for _ in range(256)]; g = [rng.randrange(3329) for _ in range(256)]
assert h.scale(h.invntt(h.basemul(h.ntt(f), h.ntt(g)))) == R.schoolbook(f, g)
print("ok")
"""


@pytest.mark.skipif(not os.path.isdir(TEAM_TEST), reason="chipathon-2026 not checked out next to this repo")
def test_team_chip_matches_team_reference():
    code = CHECK.format(model=os.path.join(ROOT, "model"), sim=os.path.join(ROOT, "sim"), team=TEAM_TEST)
    r = subprocess.run([sys.executable, "-c", code], env={**os.environ, "NTT_CHIP": "team"},
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr[-2000:]
