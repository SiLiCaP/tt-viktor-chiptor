# What can our chip do for ML-KEM with 4, 6 or 8 tiles?

This note is for deciding what to build and how many tiles to ask for. Every number comes from
`python sim/arch_explore.py`. Each one is **measured** (our RTL, synthesis, the FPGA), **cited**
(pqm4, ePrint 2022/112) or an **estimate**. Times are for the Tiny Tapeout demo board: RP2350 at
150 MHz, chip at 50 MHz, with every bit moved over the pins.

## 1. Where ML-KEM-768 spends its time on the RP2350 alone

| Operation | Total | SHA-3 / SHAKE | NTT, basemul | Everything else |
|---|---|---|---|---|
| keygen | 4.28 ms | 3.19 ms (75 %) | 0.34 ms (8 %) | 0.76 ms (18 %) |
| encaps | 4.39 ms | 3.27 ms (74 %) | 0.40 ms (9 %) | 0.73 ms (17 %) |
| decaps | 4.72 ms | 3.27 ms (69 %) | 0.58 ms (12 %) | 0.87 ms (18 %) |

These sources are cited: pqm4 m4fspeed cycles and its hashing share, and ePrint 2022/112 for the NTT
and basemul cycles. That gives hard ceilings, by Amdahl's law:

- An **infinitely fast NTT unit** gives at most **1.09–1.14×**.
- An **infinitely fast Keccak unit** gives at most **3.3–3.9×**.
- **Both together** give at most **5.4–6.0×**.

Each operation runs about **44 Keccak-f[1600] permutations**. 27 of them generate the matrix Â.
On the RP2350 a permutation costs about 11,000 cycles, or 74 µs. These counts come from instrumenting
`model/mlkem.py`.

## 2. What the blocks cost in area

| Block | Synthesized area (sky130) | Source |
|---|---|---|
| our NTT coprocessor (design A) | 20,000 µm² | measured |
| parallel 12×12 K-RED multiplier (1 product / clock) | 7,000 µm² | measured, **same size as our serial one** (7,200) |
| Keccak-f[1600], 1 round per clock | 145,000 µm² | measured (32k state + ~110k round logic) |
| Keccak, 320-bit plane-serial datapath | ~70,000 µm² | estimate |
| Keccak, 64-bit lane-serial datapath | ~50,000 µm² | estimate |
| one polynomial stored on chip (256 × 12 bit) | ~60,000–80,000 µm² | estimate (flip-flops or latches + read mux) |
| ML-KEM-768 decapsulation key on chip (2,400 B) | > 280,000 µm² | estimate |

Budget for synthesized logic: our 2×2 harden needed 1.6× the synthesized area once placed (measured),
and placement tops out around 70 % density. That gives about **32k µm² for 2×2, 48k for 3×2 and 63k for
4×2** (estimate).

## 3. Options

| Design | Area | Fits | One key exchange | vs. RP2350 alone |
|---|---|---|---|---|
| RP2350 alone | – | – | 13.4 ms | 1.00× |
| today: NTT engine A | 20k | 2×2 | 15.6 ms | 0.86× |
| A + parallel multiplier | 20k | 2×2 | 14.5 ms | 0.93× |
| NTT block engine (B3) + parallel multiplier | 36k | 3×2 | 13.3 ms | 1.01× |
| **Keccak lane-serial, arithmetic stays on the RP2350** | ~50k | **4×2** | **8.1 ms** | **1.65×** |
| Keccak lane-serial + NTT A | ~70k | no (9 tiles) | 9.2 ms | 1.46× |
| Keccak plane-serial | ~70k | no (9 tiles, borderline) | 4.8 ms | 2.78× |
| Keccak 1 round / clock | 145k | no (18 tiles) | 4.2 ms | 3.17× |

Chart: `reports/perf/05_architecture_options.png`.

## 4. What this means

1. **"Load the key, run everything on chip, read it out" does not fit, not even in 8 tiles.**
   ML-KEM needs several 256-coefficient polynomials at once, and a single one costs more area than
   8 tiles of logic. Keys and polynomials have to stay in the RP2350's 520 KB of SRAM.
   If area were unlimited (about 50 tiles), the chip could run a whole operation in roughly
   8,000 clocks, or 0.16 ms. That's about 25× faster than the RP2350, but it isn't available on a
   Tiny Tapeout shuttle.
2. **Bigger math blocks don't buy much on their own.**
   - The parallel multiplier is free in area, and it makes basemul 3× faster.
   - The NTT is still limited by the pins: 3 result bytes per butterfly.
   - Keeping 16 coefficients on chip (design B3) gets the NTT below the RP2350's software time, but
     the arithmetic is only 8–12 % of ML-KEM, so the whole operation barely moves.
3. **Hashing is where the time is.**
   - A Keccak unit is the only accelerator that can make ML-KEM clearly faster.
   - A compact lane-serial Keccak (~50k µm²) fits in **4×2**: about **1.65×** for the whole key
     exchange.
   - A plane-serial one would reach about **2.8×**, but needs a little more than 8 tiles by this
     estimate. With careful design (latch-based state, a shared datapath) it may just fit.
4. **One Tiny Tapeout chip runs only one project at a time** (the mux selects one design). Two separate
   2×2 projects, one NTT and one Keccak, could not work together on a key exchange. It has to be **one
   4×2 project**.
5. Clocking faster doesn't help much: the chip runs from the board's clock (assumed limit about 50 MHz),
   and a 1-round-per-clock Keccak would likely not even close timing at 50 MHz.

## 5. Suggested plan if we get 8 tiles (4×2)

- **Phase 1 (done):** NTT engine A, verified on RTL, gate level and FPGA. It stays useful as the
  arithmetic demo, and as the masking and side-channel story.
- **Phase 2:** a lane-serial Keccak-f[1600] with SHAKE/SHA-3 padding and rate control, on the same
  12-bit-in / 8-bit-out pin protocol. Synthesize it early, because the 50k µm² figure is an estimate.
- **Phase 3, if it fits:** on-chip SampleNTT (rejection sampling). The RP2350 then gets Â coefficients
  directly instead of SHAKE bytes, which cuts 27 permutations' worth of output parsing on the CPU.
- Swap in the parallel multiplier now: it costs no area and makes basemul 3× faster.

If only 6 tiles (3×2) are available: the lane-serial Keccak alone is over budget by the estimate.
That makes the B3 block engine the most useful 3×2 design, at about 1.0×.
