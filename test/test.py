# SPDX-FileCopyrightText: © 2026 Marks Hansons
# SPDX-License-Identifier: Apache-2.0
"""Top-level tests of tt_um_ntt_engine: every clock's uo_out is compared with the cycle-accurate Python
chip model (sim/chip_a.py), which itself is checked against FIPS 203 in test/py.

Pin timing: in each clock the inputs are applied and uo_out is sampled at the falling edge, then the
rising edge happens, the same convention as the models, the stimulus files and the Tang Nano rig.
"""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, d) for d in ("model", "sim")]

import chip_arith as C  # noqa: E402
from chip_a import ChipA  # noqa: E402
from export import read  # noqa: E402
from host import Host  # noqa: E402
from mlkem import PARAMS  # noqa: E402
from pins import PinIn  # noqa: E402
from protocol import LAT, OP_BASEMUL, OP_CT, OP_SCALE, unpack_pair  # noqa: E402


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())     # 50 MHz
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1


async def play(dut, words):
    """words: 16-bit {uio_in, ui_in} per clock -> uo_out per clock. Call right after reset()."""
    out = []
    for w in words:
        out.append(int(dut.uo_out.value))
        dut.ui_in.value = w & 0xFF
        dut.uio_in.value = w >> 8
        await FallingEdge(dut.clk)
        assert int(dut.uio_oe.value) == 0 and int(dut.uio_out.value) == 0
    return out


def model(words):
    chip = ChipA()
    return [chip.step(w & 0xFF, w >> 8) for w in words]


def compare(got, exp, what):
    for i, (g, e) in enumerate(zip(got, exp)):
        assert g == e, f"{what}: first mismatch at clock {i}: uo_out={g:#04x}, expected {e:#04x}"
    assert len(got) == len(exp)


def w(din, sof=False, op=0, valid=True):
    return PinIn(din, valid, sof, op).word16()


IDLE = 0


@cocotb.test()
async def test_spec_worked_values(dut):
    """Worked examples from team Specs 2-5."""
    await reset(dut)
    seq = ([w(2000, True, OP_CT), w(1000, False, OP_CT)] + [IDLE] * 10                   # forward bf
           + [w(13, True, OP_BASEMUL), w(7, False, OP_BASEMUL), w(11, False, OP_BASEMUL),
              w(5, False, OP_BASEMUL)] + [IDLE] * 24                                     # basemul g1 f1 g0 f0
           + [w(169, True, OP_SCALE), IDLE, IDLE, w(1275, False, OP_SCALE)] + [IDLE] * 12)
    got = await play(dut, seq)
    compare(got, model(seq), "worked values")
    assert unpack_pair(*got[LAT[OP_CT]:LAT[OP_CT] + 3]) == (169, 1831)
    b0 = 12 + LAT[OP_BASEMUL]
    assert unpack_pair(*got[b0:b0 + 3]) == (1089, 695)          # piece 0: gamma = 17, as in Spec 3
    assert unpack_pair(*got[b0:b0 + 3]) == C.basemul_piece(5, 7, 11, 13, 0)
    s0 = 40 + LAT[OP_SCALE]
    assert unpack_pair(*got[s0:s0 + 3]) == (3303, 316)


async def replay_file(dut, name):
    await reset(dut)
    stim, exp = read(os.path.join(ROOT, "test", "stimulus", f"{name}.txt"))
    compare(await play(dut, stim), exp, name)


@cocotb.test()
async def test_replay_stimulus_a(dut):
    """Stage 1 stimulus file: forward NTT, inverse NTT, scale, basemul, cycle-exact."""
    await replay_file(dut, "a")


@cocotb.test()
async def test_replay_stimulus_a_shuffle(dut):
    await replay_file(dut, "a_shuffle")


@cocotb.test()
async def test_cancel_idle_and_extra_inputs(dut):
    """Valid words outside a job are ignored, extra inputs after a job are ignored, a new sof cancels
    and flushes (Spec 3). Random legal fragments, compared clock by clock with the model."""
    rng = random.Random(7)
    seq = [w(rng.randrange(3329)) for _ in range(5)] + [IDLE] * 3        # no sof: ignored
    for _ in range(12):
        op = rng.randrange(4)
        units = rng.randrange(1, 6)
        offs = {0: (0, 1), 1: (0, 1), 2: (0, 1, 2, 3), 3: (0, 3)}[op]
        period = {0: 3, 1: 3, 2: 15, 3: 6}[op]
        frag = []
        for u in range(units):
            unit = [IDLE] * period
            for k, o in enumerate(offs):
                unit[o] = w(rng.randrange(3329), sof=(u == 0 and k == 0), op=op)
            frag += unit
        seq += frag + [IDLE] * rng.randrange(0, 25)          # often cancelled by the next sof
    seq += [IDLE] * 30
    await reset(dut)
    compare(await play(dut, seq), model(seq), "cancel/idle")


async def mlkem_trace(dut, ps):
    """Stage 4: record keygen, encaps, decaps (and implicit rejection) through the host model,
    then replay on the RTL. Matching every uo_out means the RTL drives the same ML-KEM run."""
    rng = random.Random(ps)
    host = Host(ChipA(), record=True)
    kem, ref = PARAMS[ps](host), PARAMS[ps]()
    d, z, m = (rng.randbytes(32) for _ in range(3))
    ek, dk = kem.keygen_internal(d, z)
    K, c = kem.encaps_internal(ek, m)
    assert kem.decaps(dk, c) == K
    assert (ek, dk) == ref.keygen_internal(d, z) and (K, c) == ref.encaps_internal(ek, m)
    await reset(dut)
    compare(await play(dut, host.trace.stim), host.trace.expect, ps)
    dut._log.info(f"{ps}: {len(host.trace.stim)} clocks, {len(host.stats)} chip calls, all bytes match")


@cocotb.test()
async def test_mlkem512_through_rtl(dut):
    await mlkem_trace(dut, "ML-KEM-512")


@cocotb.test()
async def test_mlkem768_through_rtl(dut):
    await mlkem_trace(dut, "ML-KEM-768")
