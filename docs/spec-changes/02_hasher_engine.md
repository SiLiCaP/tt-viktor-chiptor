# Spec change 2: a SHA-3 / SHAKE (Keccak) engine next to the NTT coprocessor

**For:** the team. **Base:** `chipathon-2026` at `bb17782`, plus change 1 (full-rate multiplier).
**Status:** proposal, with a fit check. Read the fit check first.

## 0. Fit check: it does **not** fit in 4×2 (8 tiles)

All areas are sky130 hd, Yosys + ABC, typical corner:

| Block | Synthesized area | Source |
|---|---|---|
| team chip `tt_um_NTT_Core` (I/O, control, ROM, multiplier, adders) | **22,903 µm²** | measured, chipathon-2026 `bb17782` |
| Keccak-f[1600], lane-serial, 1,346 clocks / permutation | **151,452 µm²** | measured, RTL verified against hashlib (`tt-viktor-chiptor/sim/arch_explore_rtl/keccak_lane.v`) |
| Keccak-f[1600], 1 round / clock, 24 clocks / permutation | 145,288 µm² | measured |
| lane-serial with clock-gated registers instead of enable flip-flops | ~110,000 µm² | estimate |
| sponge control, byte I/O, command decode | ~5,000 µm² | estimate |

What 4×2 holds: about 145,000 µm² of core area. Our 2×2 harden needed 1.6× its synthesized area once
placed (measured), and placement tops out near 70 % density. That leaves about 63,000 µm² of synthesized
logic for 4×2 (estimate).

- **The Keccak core alone is larger than the whole 4×2 core area.** The 1,600 state bits dominate. Each
  needs a write-enabled flip-flop (30 µm²), and the core reads lanes through a 25:1 mux. That's about
  92,000 µm² of flip-flops before any logic.
- NTT chip + Keccak + glue ≈ **179,000 µm²** synthesized, about 2.8× the 4×2 budget. It would need about
  **23 tiles**, and Tiny Tapeout's largest project is 8×2 = 16 tiles.
- Even the best case (clock-gated registers, NTT chip dropped, ~110,000 µm²) needs about 14 tiles.
- **Latch-based state storage** (one latch per bit plus a read mux, like the DFFRAM macros) might bring
  the core to about 70–80k µm². That's about 10 tiles: still over 8, unverified, and latches complicate
  timing signoff in the TT flow.

**Conclusion:** the hashing speedup can't be built in 8 tiles. If it fit, the measured core would give
**1.73×** for ML-KEM-512 (better than the 1.64× estimated earlier, because the measured core is faster:
1,346 vs 1,500 clocks per permutation). The rest of this document is the spec work needed if a larger
area (≥ 14–16 tiles) or a denser storage option becomes available.

## 1. What the engine would do

The RP2350 keeps polynomials, keys, sampling, encoding and the NTT arithmetic. The NTT is faster in
M33 software than on the pin-bound chip; that's measured, see `docs/FPGA_DEMO.md`. The chip takes over
every Keccak call of ML-KEM-512:

Permutations per operation (keygen / encaps / decaps):

| Call | Permutations each | keygen | encaps | decaps |
|---|---|---|---|---|
| G = SHA3-512 | 1 | 1 | 1 | 1 |
| H = SHA3-256 of ek (800 B) | 6 | 6 (stored in dk) | 6 | – |
| J = SHAKE256 of z‖c (800 B) | 6 | – | – | 6 |
| PRF, η = 3 (192 B out) | 2 | 4 calls = 8 | 2 calls = 4 | 2 calls = 4 |
| PRF, η = 2 (128 B out) | 1 | – | 3 calls = 3 | 3 calls = 3 |
| XOF = SHAKE128 for Â (4 polynomials) | about 3 | 12 | 12 | 12 |
| **total** (matches the model's measured count) | | **27** | **26** | **26** |

Time per permutation: 1,346 clocks = 26.9 µs at 50 MHz, against about 74 µs on the RP2350.
Absorbing goes 1 byte per clock in, squeezing 1 byte per clock out. About 1.1 kB in and 2.7 kB out
per operation, so I/O is small next to the permutations.

## 2. New Spec 6: Keccak engine (new owner)

Module `keccak_lane` (reference RTL and test in `tt-viktor-chiptor/sim/arch_explore_rtl/`):

| Port | Dir | Width | Meaning |
|---|---|---|---|
| `clk`, `rst_n` | in | 1 | as everywhere |
| `start` | in | 1 | run one Keccak-f[1600] permutation (ignored while busy) |
| `busy` | out | 1 | high for exactly 1,345 clocks after `start` |
| `io_we`, `io_idx`, `io_wdata` | in | 1, 5, 64 | while idle: lane[io_idx] ^= io_wdata (absorb) |
| `io_rdata` | out | 64 | while idle: lane[io_idx] (squeeze) |

Requirements:
- Fixed latency (constant time).
- Verified against FIPS 202, as `keccak_ref.py` and `test_keccak_lane.py` already do.
- Area target under the agreed budget, with clock-gated registers or latch storage.

New module `sponge_ctrl` (Control owner or the new owner):
- **Modes:** SHA3-256 (rate 136, pad 0x06), SHA3-512 (rate 72, 0x06), SHAKE128 (rate 168, 0x1F),
  SHAKE256 (rate 136, 0x1F).
- **Absorb:** an 8-byte assembler XORs one lane per 8 bytes. After `rate` bytes, start a permutation.
  On the last byte, pad (pad byte, then 0x80 in the last rate byte) and permute.
- **Squeeze:** stream `rate` bytes out of the lanes, one per clock, through an 8-byte shifter. A
  "more" command permutes and streams the next block.

## 3. Changes to the existing specs

### Spec 5 (I/O): the pins stay as they are
- **Command words.** `valid` + `sof` with `din` ≥ 3329 can't be a coefficient, so it is a command
  (`din[11:8]` = 0xF). `din[3:0]`: 0 SHA3-256, 1 SHA3-512, 2 SHAKE128, 3 SHAKE256, 4 squeeze more.
  `din[7:4]` is reserved and must be 0. `op` is ignored on a command word.
- **Data words in hash mode:** `din[7:0]` is a byte and `din[8]` marks the last byte. `din[11:9]` must be 0.
- **Output:** `uo_out` is a mux between `io_out_pack` (NTT jobs) and the sponge's byte shifter (hash jobs).
  The engine that owns the current job drives it, and the other side outputs 0.

### Spec 3 (Control)
- **Job start:** a sof word with `din` < 3329 starts an NTT job as today; a command word starts a hash
  job. A new sof of either kind cancels the running job and flushes both engines.
- **Fixed hash timing**, for the host's `timing.py`:
  - absorb: 1 byte per clock, any number of `valid`-low clocks allowed between bytes;
  - after every `rate`-th byte or the last byte, a permutation of 1,345 clocks during which input is ignored;
  - squeeze: byte k of a block comes out at a fixed offset after the permutation ends (offset to be
    published by Control, like D).
- `pair_valid` and the packer are unaffected in hash mode.

### Spec 1 (Pi harness)
- New host calls `sha3_256`, `sha3_512`, `shake128(in, n)`, `shake256(in, n)`, each a command word +
  data bytes, then reading the output bytes at the fixed offsets.
- ML-KEM on the host routes G, H, J, PRF and XOF through these calls. SampleNTT (rejection sampling)
  parses the SHAKE128 bytes on the RP2350.
- New timing constants: permutation length, squeeze offset, the bytes-per-clock rates.

### Specs 2 and 4
No change.

### info.yaml
`tiles` grows to whatever size the fit check settles on, more than "4x2" by the numbers in section 0.

## 4. Verification plan

1. `keccak_lane` against FIPS 202 (done for the permutation: 6 random states, cycle count fixed at 1,346).
2. `sponge_ctrl` against hashlib for all four modes, message lengths 0, 1, rate−1, rate, rate+1, 800.
3. Whole chip: ML-KEM-512 keygen/encaps/decaps with hashing on the chip, byte-identical to FIPS 203,
   in cocotb and on the Tang Nano (the host side exists in `tt-viktor-chiptor/host`).
4. **Fit:** harden the integrated top at the target tile size before committing to it.
