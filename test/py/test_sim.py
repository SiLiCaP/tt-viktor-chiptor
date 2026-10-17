"""Stage 1: pin-level chip models + host model (sim/) against the golden model and FIPS 203."""
import os
import random

import pytest

from chip_a import ChipA, ProtocolError
from chip_b import ChipB
from host import make_host
from mlkem import PARAMS, ReferenceBackend
from mlkem_ntt_model import Q, basemul_ref, ntt_ref
from pins import PinIn
from protocol import LAT, OP_CT, block_period

VARIANTS = [("A", "serial", False), ("A", "parallel", False), ("A", "serial", True),
            ("B", "serial", False), ("B", "parallel", False), ("B", "serial", True), ("B", "parallel", True)]
VID = [f"{d}-{m}{'-shuffle' if s else ''}" for d, m, s in VARIANTS]
REF = ReferenceBackend()


def rpoly(rng):
    return [rng.randrange(Q) for _ in range(256)]


@pytest.mark.parametrize("design,mult,shuffle", VARIANTS, ids=VID)
def test_ops_match_golden(design, mult, shuffle):
    rng = random.Random(f"{design}{mult}{shuffle}")
    h = make_host(design, mult, shuffle, seed=1)
    for _ in range(5):
        f, g = rpoly(rng), rpoly(rng)
        assert h.ntt(f) == ntt_ref(f)
        assert h.invntt(f) == REF.invntt(f)
        assert h.scale(f) == REF.scale(f)
        assert h.basemul(f, g) == basemul_ref(f, g)
    assert all(s.stalls == 0 for s in h.stats)


def test_cycle_counts():
    """Section 4 clocks per NTT plus the fixed protocol overhead.
    A: 896 butterflies x 3 clocks = 2688, plus LAT (the last result arrives LAT clocks after its word).
    B: handoff 3968 (B1) / 2176 (B2) count 16 in + compute + 24 out per block. The protocol adds
       1 header clock and a 3-clock PE drain per block: 32 x 4 = +128."""
    for mult, extra in (("serial", LAT["serial"][OP_CT]), ("parallel", LAT["parallel"][OP_CT])):
        h = make_host("A", mult)
        h.ntt([0] * 256)
        assert h.stats[-1].clocks == 2688 + extra
    for mult, handoff in (("serial", 3968), ("parallel", 2176)):
        h = make_host("B", mult)
        h.ntt([0] * 256)
        assert h.stats[-1].clocks == 16 * (block_period(0, mult) + block_period(1, mult)) == handoff + 128


@pytest.mark.parametrize("design,mult", [("A", "serial"), ("A", "parallel"), ("B", "serial"), ("B", "parallel")])
def test_constant_time(design, mult):
    """Section 5.1: identical input-valid and output-valid pattern for any data, and in B for shuffle on/off."""
    rng = random.Random(5)
    inputs = [[0] * 256, [Q - 1] * 256, rpoly(rng), rpoly(rng)]
    patterns = set()
    for i, f in enumerate(inputs):
        for shuffle in ((False, True) if design == "B" else (False,)):
            h = make_host(design, mult, shuffle, record=True, seed=i)
            h.ntt(f); h.invntt(f); h.scale(f); h.basemul(f, inputs[0])
            in_pat = tuple((w >> 12) for w in h.trace.stim)        # valid, sof, op pins only
            patterns.add((in_pat, tuple(h.trace.out_valid), tuple(s.clocks for s in h.stats)))
    assert len(patterns) == 1


def test_a_host_shuffle_changes_order_not_result():
    """Shuffled runs add a fixed LAT gap per layer; timing must not depend on the permutation."""
    rng = random.Random(9)
    f = rpoly(rng)
    runs = []
    for seed in range(8):
        h = make_host("A", shuffle=True, record=True, seed=seed)
        assert h.ntt(f) == ntt_ref(f) and h.invntt(f) == REF.invntt(f)
        assert all(s.stalls == 0 for s in h.stats)
        runs.append(h.trace)
    assert len({tuple(r.stim) for r in runs}) == len(runs)          # different bus traffic every time
    assert len({(tuple(w >> 12 for w in r.stim), tuple(r.out_valid)) for r in runs}) == 1   # same timing


def test_b_lfsr_shuffle_changes_order():
    h = make_host("B", shuffle=True)
    h.ntt([1] * 256)
    assert h.chip.orders != [list(range(8))] * len(h.chip.orders)


def test_masking_share_traffic_uniform():
    """Section 5.2: host-side masking. s = s1 + s2 (s1 uniform). NTT is linear, so
    NTT(s1) + NTT(s2) = NTT(s). The words the host puts on the bus for one share look uniform."""
    rng = random.Random(11)
    s = [rng.choice((0, 1, 2, Q - 1, Q - 2)) for _ in range(256)]     # small secret, CBD-like
    s1 = rpoly(rng)
    s2 = [(a - b) % Q for a, b in zip(s, s1)]
    h = make_host("A", record=True)
    r = [(a + b) % Q for a, b in zip(h.ntt(s1), h.ntt(s2))]
    assert r == ntt_ref(s)
    # chi-square of the first frame's data words (share s1) against uniform [0, q), 16 bins
    stim = h.trace.stim[:len(h.trace.stim) // 2]
    data = [((w >> 8) & 0xF) << 8 | (w & 0xFF) for w in stim if (w >> 12) & 1]
    bins = [0] * 16
    for x in data:
        bins[x * 16 // Q] += 1
    exp = len(data) / 16
    chi2 = sum((b - exp) ** 2 / exp for b in bins)
    assert chi2 < 37.7            # p = 0.001 for 15 degrees of freedom
    # the unmasked secret is visibly non-uniform on the bus
    h2 = make_host("A", record=True)
    h2.ntt(s)
    first_layer = [((w >> 8) & 0xF) << 8 | (w & 0xFF) for w in h2.trace.stim[:3 * 128] if (w >> 12) & 1]
    assert len(set(first_layer)) <= 5


def test_protocol_violations_detected():
    chip = ChipA("serial")
    word = lambda din, sof=False: PinIn(din, True, sof, OP_CT).encode()
    chip.step(*word(1, sof=True)); chip.step(*word(2))
    with pytest.raises(ProtocolError):           # next transaction 1 clock too early (period 3)
        chip.step(*word(3))
    chip = ChipB("serial")
    with pytest.raises(ProtocolError):           # data before any header
        chip.step(*word(1))


SEEDS = int(os.environ.get("MLKEM_SEEDS", "10"))     # acceptance run: MLKEM_SEEDS=100


@pytest.mark.parametrize("design,mult,shuffle", VARIANTS, ids=VID)
@pytest.mark.parametrize("ps", ["ML-KEM-512", "ML-KEM-768"])
def test_mlkem_through_chip(ps, design, mult, shuffle):
    rng = random.Random(f"{ps}{design}{mult}{shuffle}")
    ref = PARAMS[ps]()
    kem = PARAMS[ps](make_host(design, mult, shuffle, seed=2))
    for _ in range(SEEDS):
        d, z, m = (rng.randbytes(32) for _ in range(3))
        ek, dk = kem.keygen_internal(d, z)
        assert (ek, dk) == ref.keygen_internal(d, z)
        K, c = kem.encaps_internal(ek, m)
        assert (K, c) == ref.encaps_internal(ek, m)
        assert kem.decaps(dk, c) == K
        bad = bytes([c[0] ^ 1]) + c[1:]
        assert kem.decaps(dk, bad) == ref.decaps(dk, bad)


@pytest.mark.parametrize("variant", ["a_serial", "a_parallel", "a_serial_shuffle", "b_serial",
                                     "b_parallel", "b_serial_shuffle", "b_parallel_shuffle"])
def test_stimulus_files_current(variant):
    """test/stimulus/*.txt (replayed by cocotb and the Tang Nano) must match the current models.
    If this fails after a protocol change, regenerate with: python sim/export.py"""
    from conftest import ROOT
    from export import generate, read
    stim, exp = read(os.path.join(ROOT, "test", "stimulus", f"{variant}.txt"))
    t = generate(variant)
    assert (stim, exp) == (t.stim, t.expect)
