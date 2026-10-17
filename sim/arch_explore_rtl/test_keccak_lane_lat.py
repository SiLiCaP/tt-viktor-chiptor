"""cocotb: keccak_lane_lat.v against keccak_ref.keccak_f (random states), clock count."""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

sys.path.insert(0, os.path.dirname(__file__))
from keccak_ref import keccak_f  # noqa: E402


@cocotb.test()
async def test_permutation(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.rst_n.value = 0; dut.io_ovw.value = 0; dut.start.value = 0; dut.io_we.value = 0; dut.io_idx.value = 0; dut.io_wdata.value = 0
    await ClockCycles(dut.clk, 3)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.io_ovw.value = 1                         # latches have no reset: clear the state through the port
    for i in range(25):
        dut.io_we.value = 1; dut.io_idx.value = i; dut.io_wdata.value = 0
        await FallingEdge(dut.clk)
    dut.io_we.value = 0; dut.io_ovw.value = 0
    rng = random.Random(1)
    state = [0] * 25
    for trial in range(6):
        new = [rng.getrandbits(64) for _ in range(25)] if trial else [0] * 25
        for i in range(25):                      # absorb: A[i] ^= new[i]
            dut.io_we.value = 1; dut.io_idx.value = i; dut.io_wdata.value = new[i]
            await FallingEdge(dut.clk)
            state[i] ^= new[i]
        dut.io_we.value = 0
        dut.start.value = 1
        await FallingEdge(dut.clk)
        dut.start.value = 0
        clocks = 1
        while int(dut.busy.value):
            await FallingEdge(dut.clk)
            clocks += 1
        state = keccak_f(state)
        for i in range(25):
            dut.io_idx.value = i
            await FallingEdge(dut.clk)
            assert int(dut.io_rdata.value) == state[i], f"trial {trial} lane {i}"
        dut._log.info(f"trial {trial}: permutation OK, {clocks} clocks")
