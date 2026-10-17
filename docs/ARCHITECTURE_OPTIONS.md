# What can our chip do for ML-KEM-512 with 4, 6 or 8 tiles?

This note is for deciding what to build and how many tiles to ask for. Our target is **ML-KEM-512**;
`python sim/arch_explore.py ML-KEM-768` gives the same tables for 768 (the speedups come out within 0.03×).
Every number comes from `python sim/arch_explore.py`. Each one is **measured** (our RTL, synthesis, the FPGA), **cited**
(pqm4, ePrint 2022/112) or an **estimate**. Times are for the Tiny Tapeout demo board: RP2350 at
150 MHz, chip at 50 MHz, with every bit moved over the pins.

## 1. Where ML-KEM-512 spends its time on the RP2350 alone

| Operation | Total | SHA-3 / SHAKE | NTT, basemul | Everything else |
|---|---|---|---|---|
| keygen | 2.62 ms | 1.98 ms (76 %) | 0.20 ms (8 %) | 0.44 ms (17 %) |
| encaps | 2.61 ms | 1.92 ms (73 %) | 0.25 ms (10 %) | 0.44 ms (17 %) |
| decaps | 2.85 ms | 1.92 ms (67 %) | 0.39 ms (14 %) | 0.55 ms (19 %) |

These sources are cited: pqm4 m4fspeed cycles and its hashing share, and ePrint 2022/112 for the NTT
and basemul cycles. That gives hard ceilings, by Amdahl's law:

- An **infinitely fast NTT unit** gives at most **1.08–1.16×**.
- An **infinitely fast Keccak unit** gives at most **3.0–4.1×**.
- **Both together** give at most **5.2–6.0×**.

Each operation runs about **26–27 Keccak-f[1600] permutations** (768: about 44). 12 of them generate the
2×2 matrix Â. On the RP2350 a permutation costs about 11,000 cycles, or 74 µs. These counts come from
instrumenting `model/mlkem.py`.

## 2. What the blocks cost in area

| Block | Synthesized area (sky130) | Source |
|---|---|---|
| our NTT coprocessor (design A) | 20,000 µm² | measured |
| parallel 12×12 K-RED multiplier (1 product / clock) | 7,000 µm² | measured, **same size as our serial one** (7,200) |
| Keccak-f[1600], 1 round per clock | 145,000 µm² | measured (32k state + ~110k round logic) |
| Keccak, 320-bit plane-serial datapath | ~70,000 µm² | estimate |
| Keccak, 64-bit lane-serial datapath | ~50,000 µm² | estimate |
| one polynomial stored on chip (256 × 12 bit) | ~60,000–80,000 µm² | estimate (flip-flops or latches + read mux) |
| ML-KEM-512 decapsulation key on chip (1,632 B) | > 190,000 µm² | estimate |

Budget for synthesized logic: our 2×2 harden needed 1.6× the synthesized area once placed (measured),
and placement tops out around 70 % density. That gives about **32k µm² for 2×2, 48k for 3×2 and 63k for
4×2** (estimate).

## 3. Options

| Design | Area | Fits | One key exchange | vs. RP2350 alone |
|---|---|---|---|---|
| RP2350 alone | – | – | 8.08 ms | 1.00× |
| today: NTT engine A | 20k | 2×2 | 9.38 ms | 0.86× |
| A + parallel multiplier | 20k | 2×2 | 8.82 ms | 0.92× |
| NTT block engine (B3) + parallel multiplier | 36k | 3×2 | 7.97 ms | 1.01× |
| **Keccak lane-serial, arithmetic stays on the RP2350** | ~50k | **4×2** | **4.91 ms** | **1.64×** |
| Keccak lane-serial + NTT A | ~70k | no (9 tiles) | 5.65 ms | 1.43× |
| Keccak plane-serial | ~70k | no (9 tiles, borderline) | 2.94 ms | 2.75× |
| Keccak 1 round / clock | 145k | no (18 tiles) | 2.58 ms | 3.13× |

Chart: `reports/perf/05_architecture_options.png`.

## 4. What this means

1. **"Load the key, run everything on chip, read it out" does not fit, not even in 8 tiles.**
   ML-KEM needs several 256-coefficient polynomials at once, and a single one costs more area than
   8 tiles of logic. Keys and polynomials have to stay in the RP2350's 520 KB of SRAM.
   If area were unlimited (about 40 tiles for ML-KEM-512), the chip could run a whole operation in a few
   thousand clocks, about 0.1 ms. That's roughly 25× faster than the RP2350, but it isn't available on a
   Tiny Tapeout shuttle.
2. **Bigger math blocks don't buy much on their own.**
   - The parallel multiplier is free in area, and it makes basemul 3× faster.
   - The NTT is still limited by the pins: 3 result bytes per butterfly.
   - Keeping 16 coefficients on chip (design B3) gets the NTT below the RP2350's software time, but
     the arithmetic is only 8–12 % of ML-KEM, so the whole operation barely moves.
3. **Hashing is where the time is.**
   - A Keccak unit is the only accelerator that can make ML-KEM clearly faster.
   - A compact lane-serial Keccak (~50k µm²) fits in **4×2**: about **1.64×** for the whole key
     exchange.
   - A plane-serial one would reach about **2.75×**, but needs a little more than 8 tiles by this
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
