# Exploration RTL (not part of the chip)

Written to measure sky130 area for `sim/arch_explore.py`. `keccak_lane.v` is verified (cocotb, `make -C sim/arch_explore_rtl`, against `keccak_ref.py`, which matches hashlib); the others are area models only.

| File | What | Synthesized area (sky130 hd, tt corner, Yosys + ABC) |
|---|---|---|
| `keccak_core.v` | Keccak-f[1600], 1 round per clock (`ROUNDS_PER_CLK=1`) or 2 | 142,355 µm² (1 round), 216,615 µm² (2 rounds) |
| `keccak_core.v` + shifting lane I/O | same round, absorb/squeeze by shifting lanes | 145,288 µm² (state 32k + round logic ~110k) |
| `keccak_lane.v` | lane-serial Keccak-f[1600], 1,346 clocks per permutation, verified | 151,452 µm² |
| `mul_par.v` | 12×12 multiply + two K-RED rounds, 1 product per clock | 7,022 µm² (vs. 7,221 µm² for our serial `modq_mul`) |

Reproduce: `yosys -p "read_verilog -sv <file>; synth -flatten -top <module>; dfflibmap -liberty <lib>; abc -liberty <lib>; stat -liberty <lib>"`
with `sky130_fd_sc_hd__tt_025C_1v80.lib`.
