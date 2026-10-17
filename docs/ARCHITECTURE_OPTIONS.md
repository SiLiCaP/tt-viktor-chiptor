# What can our chip do for ML-KEM-512 with 4, 6 or 8 tiles?

This note is for deciding what to build and how many tiles to ask for. Our target is **ML-KEM-512**;
`python sim/arch_explore.py ML-KEM-768` gives the same tables for 768. Every number comes from
`python sim/arch_explore.py`. Each one is **measured** (RTL, synthesis, the FPGA), **cited** (pqm4,
ePrint 2022/112) or an **estimate**. Times are for the Tiny Tapeout demo board: RP2350 at 150 MHz,
chip at 50 MHz, with every bit moved over the pins.

**Correction (Oct 17).** An earlier version of this note claimed a lane-serial Keccak (~50k µm²) would fit
in 4×2 for 1.64×. Built, verified and synthesized, the core is **151k µm²**. No hashing engine fits in
8 tiles. The detailed fit check is in `docs/spec-changes/02_hasher_engine.md`.

## 1. Where ML-KEM-512 spends its time on the RP2350 alone

| Operation | Total | SHA-3 / SHAKE | NTT, basemul | Everything else |
|---|---|---|---|---|
| keygen | 2.62 ms | 1.98 ms (76 %) | 0.20 ms (8 %) | 0.44 ms (17 %) |
| encaps | 2.61 ms | 1.92 ms (73 %) | 0.25 ms (10 %) | 0.44 ms (17 %) |
| decaps | 2.85 ms | 1.92 ms (67 %) | 0.39 ms (14 %) | 0.55 ms (19 %) |

The ceilings, by Amdahl's law:
- an infinitely fast NTT unit gives at most **1.08–1.16×**;
- an infinitely fast Keccak unit gives at most **3.0–4.1×**;
- both together give at most **5.2–6.0×**.

Each operation runs 26–27 Keccak-f[1600] permutations, about 74 µs each on the RP2350.

## 2. Block areas

| Block | Synthesized area (sky130) | Source |
|---|---|---|
| team chip `tt_um_NTT_Core` | 22,903 µm² | measured |
| our NTT coprocessor | 20,042 µm² | measured |
| full-rate K-RED multiplier (team, 3 rounds) | 8,785 µm² | measured |
| Keccak-f[1600], lane-serial, 1,346 clocks / permutation | **151,452 µm²** | measured, RTL verified |
| Keccak-f[1600], 1 round / clock, 24 clocks | 145,288 µm² | measured |
| lane-serial with clock-gated registers | ~110,000 µm² | estimate |
| one polynomial stored on chip | ~60,000–80,000 µm² | estimate |

Budget for synthesized logic: about 32k µm² for 2×2, 48k for 3×2 and 63k for 4×2. That's an estimate:
our 2×2 harden needed 1.6× the synthesized area once placed, at up to ~70 % density.

The Keccak state is what makes it expensive: 1,600 bits that each need a write enable, plus a lane read
mux. That's about 92k µm² of flip-flops before any logic. Doing it serially doesn't save area; the
1-round-per-clock core is even slightly smaller.

## 3. Options

| Design | Area | Fits | One key exchange | vs. RP2350 alone |
|---|---|---|---|---|
| RP2350 alone | – | – | 8.08 ms | 1.00× |
| today's NTT chip | 20–23k | 2×2 | 9.38 ms | 0.86× |
| **+ full-rate multiplier schedule** (`spec-changes/01`) | same | 2×2 | 8.82 ms | **0.92×** |
| NTT block engine (B3) | 36k (estimate) | 3×2 | 7.97 ms | 1.01× |
| Keccak lane-serial (measured) | 151k | no (19 tiles) | 4.67 ms | 1.73× |
| Keccak lane-serial + NTT chip | 174k | no (22 tiles) | 5.98 ms | 1.35× |
| Keccak 1 round / clock | 145k | no (18 tiles) | 2.58 ms | 3.13× |

Chart: `reports/perf/05_architecture_options.png`.

## 4. What this means for the tile request

1. **No hashing engine fits in 8 tiles**, and hashing is where the time is. A real speedup over the RP2350
   needs at least ~14–19 tiles. Tiny Tapeout's largest project is 8×2 = 16 tiles.
2. **"Keys and polynomials on chip" doesn't fit either.** One polynomial costs more than 8 tiles.
3. Within 2×2–3×2 the chip sits near the RP2350's software speed: 0.92× with the full-rate schedule,
   about 1.0× with a 16-coefficient block engine in 3×2. The pins (3 result bytes per butterfly) and
   Amdahl's law (arithmetic is about 10 % of ML-KEM) cap it.
4. So the case for the chip is **not raw speed with ≤ 8 tiles**. It's what it demonstrates:
   - a verified ML-KEM arithmetic coprocessor;
   - constant-time operation;
   - side-channel exposure at the pins and the masking that fixes it (live demo);
   - the measured path from RTL through FPGA to silicon.
5. A single Tiny Tapeout chip runs one project at a time, so cooperating engines must be one project.

## 5. Recommendation

- **2×2:** adopt the full-rate schedule (`docs/spec-changes/01_full_rate_multiplier.md`). It costs no
  area and makes basemul 3× and scale 2× faster.
- **More tiles:** only worth it with a goal other than beating the RP2350. A 3×2 block engine reaches
  about 1.0×; it doesn't fit in 2×2.
- **Hashing on chip:** spec and verified core are ready (`docs/spec-changes/02_hasher_engine.md`,
  `sim/arch_explore_rtl/keccak_lane.v`) for a future shuttle with ≥ 16 tiles or denser storage.
