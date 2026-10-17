"""Pin-level chip models + host model (sim/) against the golden model, FIPS 203 and the team specs."""
import os
import random

import pytest

import chip_arith as C
from chip_a import ChipA, ProtocolError
from host import make_host
from mlkem import PARAMS, ReferenceBackend
from mlkem_ntt_model import Q, basemul_ref, ntt_ref, polymul_schoolbook
from pins import PinIn
from protocol import LAT, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE, block_period

VARIANTS = [("A", False), ("A", True), ("B", False), ("B", True)]
VID = ["A", "A-shuffle", "B", "B-shuffle"]
REF = ReferenceBackend()


def rpoly(rng):
    return [rng.randrange(Q) for _ in range(256)]


@pytest.mark.parametrize("design,shuffle", VARIANTS, ids=VID)
def test_ops_match_models(design, shuffle):
    """NTT and INTT plain; basemul = 169 * plain; scale = x * 3303 * 169^-1 (Spec 3 K-RED table)."""
    rng = random.Random(f"{design}{shuffle}")
    h = make_host(design, shuffle, seed=1)
    for _ in range(5):
        f, g = rpoly(rng), rpoly(rng)
        assert h.ntt(f) == ntt_ref(f)
        assert h.invntt(f) == REF.invntt(f)
        assert h.scale(f) == [x * 3303 * 2285 % Q for x in f] == [C.scale(x) for x in f]
        assert h.basemul(f, g) == [x * 169 % Q for x in basemul_ref(f, g)]
    assert all(s.stalls == 0 for s in h.stats)


def test_demo_flow_polymul():
    """Spec 1 demo: forward, forward, basemul, inverse, scale on the chip == schoolbook mod X^256+1."""
    rng = random.Random(4)
    f, g = rpoly(rng), rpoly(rng)
    h = make_host("A")
    r = h.scale(h.invntt(h.basemul(h.ntt(f), h.ntt(g))))
    assert r == polymul_schoolbook(f, g)


def test_cycle_counts():
    """Spec 3 rates: 3 clocks per butterfly, 15 per basemul piece, 3 per scale coefficient, plus D."""
    h = make_host("A")
    z = [0] * 256
    h.ntt(z); h.invntt(z); h.basemul(z, z); h.scale(z)
    clocks = [s.clocks for s in h.stats]
    assert clocks == [895 * 3 + LAT[OP_CT] + 3, 895 * 3 + LAT[OP_GS] + 3,
                      127 * 15 + LAT[OP_BASEMUL] + 3, 127 * 6 + LAT[OP_SCALE] + 3]
    h = make_host("B")
    h.ntt(z)
    assert h.stats[-1].clocks == 16 * (block_period(0) + block_period(1))


@pytest.mark.parametrize("design", ["A", "B"])
def test_constant_time(design):
    """Spec/handoff 5.1: identical input-valid and output-valid pattern for any data (and B shuffle on/off)."""
    rng = random.Random(5)
    inputs = [[0] * 256, [Q - 1] * 256, rpoly(rng), rpoly(rng)]
    patterns = set()
    for i, f in enumerate(inputs):
        for shuffle in ((False, True) if design == "B" else (False,)):
            h = make_host(design, shuffle, record=True, seed=i)
            h.ntt(f); h.invntt(f); h.scale(f); h.basemul(f, inputs[0])
            in_pat = tuple((w >> 12) for w in h.trace.stim)
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
    assert len({tuple(r.stim) for r in runs}) == len(runs)
    assert len({(tuple(w >> 12 for w in r.stim), tuple(r.out_valid)) for r in runs}) == 1


def test_b_lfsr_shuffle_changes_order():
    h = make_host("B", shuffle=True)
    h.ntt([1] * 256)
    assert h.chip.orders != [list(range(8))] * len(h.chip.orders)


def test_masking_share_traffic_uniform():
    """Handoff 5.2: host-side masking. NTT(s1) + NTT(s2) = NTT(s); one share's bus words look uniform."""
    rng = random.Random(11)
    s = [rng.choice((0, 1, 2, Q - 1, Q - 2)) for _ in range(256)]
    s1 = rpoly(rng)
    s2 = [(a - b) % Q for a, b in zip(s, s1)]
    h = make_host("A", record=True)
    assert [(a + b) % Q for a, b in zip(h.ntt(s1), h.ntt(s2))] == ntt_ref(s)
    stim = h.trace.stim[:len(h.trace.stim) // 2]
    data = [((w >> 8) & 0xF) << 8 | (w & 0xFF) for w in stim if (w >> 12) & 1]
    bins = [0] * 16
    for x in data:
        bins[x * 16 // Q] += 1
    exp = len(data) / 16
    assert sum((b - exp) ** 2 / exp for b in bins) < 37.7       # chi^2, p = 0.001, 15 dof
    h2 = make_host("A", record=True)
    h2.ntt(s)
    first_layer = [((w >> 8) & 0xF) << 8 | (w & 0xFF) for w in h2.trace.stim[:3 * 128] if (w >> 12) & 1]
    assert len(set(first_layer)) <= 5


def drive(chip, words):
    """words: list of PinIn or None (idle) per clock -> uo_out per clock"""
    out = []
    for w in words:
        ui, uio = (w or PinIn()).encode()
        out.append(chip.step(ui, uio))
    return out


def test_job_rules():
    """Spec 3: valid words outside a job are ignored; extra inputs after the job are ignored;
    a new sof mid-job cancels and flushes (uo_out 0 from 2 clocks after the sof pin clock)."""
    v = lambda d, sof=False, op=OP_SCALE: PinIn(d, True, sof, op)
    chip = ChipA()
    out = drive(chip, [v(5), None, None])                 # no sof: ignored
    assert out == [0, 0, 0] and not chip.sched
    # scale job: c0 at 0, c1 at 3 -> pair at D=9
    chip = ChipA()
    seq = [v(169, sof=True), None, None, v(1275)] + [None] * 10
    out = drive(chip, seq)
    assert out[9:12] == [3303 & 0xFF, ((316 & 0xF) << 4) | (3303 >> 8), 316 >> 4]
    # cancel: start a scale job, cancel with a forward-NTT sof before its pair comes out
    chip = ChipA()
    seq = [v(169, sof=True), None, None, v(1275), None, None, v(2000, sof=True, op=OP_CT), v(1000, op=OP_CT)]
    out = drive(chip, seq + [None] * 12)
    assert all(b == 0 for b in out[:6 + LAT[OP_CT]])      # scale pair (due at 9) was flushed
    t = C.mul169(2000, C.ROM_P[1])
    a_, b_ = (1000 + t) % Q, (1000 - t) % Q
    assert (a_, b_) == (169, 1831)                         # Spec 3 worked forward butterfly
    assert out[6 + LAT[OP_CT]:6 + LAT[OP_CT] + 3] == [a_ & 0xFF, ((b_ & 0xF) << 4) | (a_ >> 8), b_ >> 4]


def test_protocol_violations_detected():
    w = lambda d, sof=False: PinIn(d, True, sof, OP_CT)
    chip = ChipA()
    drive(chip, [w(1, sof=True), w(2)])
    with pytest.raises(ProtocolError):                    # next unit 1 clock early (period 3)
        drive(chip, [w(3)])
    chip = ChipA()
    drive(chip, [w(1, sof=True)])
    with pytest.raises(ProtocolError):                    # a missing at offset 1
        drive(chip, [None])


SEEDS = int(os.environ.get("MLKEM_SEEDS", "10"))     # acceptance run: MLKEM_SEEDS=100


@pytest.mark.parametrize("design,shuffle", VARIANTS, ids=VID)
@pytest.mark.parametrize("ps", ["ML-KEM-512", "ML-KEM-768"])
def test_mlkem_through_chip(ps, design, shuffle):
    rng = random.Random(f"{ps}{design}{shuffle}")
    ref = PARAMS[ps]()
    kem = PARAMS[ps](make_host(design, shuffle, seed=2))
    for _ in range(SEEDS):
        d, z, m = (rng.randbytes(32) for _ in range(3))
        ek, dk = kem.keygen_internal(d, z)
        assert (ek, dk) == ref.keygen_internal(d, z)
        K, c = kem.encaps_internal(ek, m)
        assert (K, c) == ref.encaps_internal(ek, m)
        assert kem.decaps(dk, c) == K
        bad = bytes([c[0] ^ 1]) + c[1:]
        assert kem.decaps(dk, bad) == ref.decaps(dk, bad)


@pytest.mark.parametrize("variant", ["a", "a_shuffle", "b", "b_shuffle"])
def test_stimulus_files_current(variant):
    """test/stimulus/*.txt (replayed by cocotb and the Tang Nano) must match the current models.
    If this fails after a protocol change, regenerate with: python sim/export.py"""
    from conftest import ROOT
    from export import generate, read
    stim, exp = read(os.path.join(ROOT, "test", "stimulus", f"{variant}.txt"))
    t = generate(variant)
    assert (stim, exp) == (t.stim, t.expect)
