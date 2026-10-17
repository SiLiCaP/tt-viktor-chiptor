# Options for 4 tiles and for 8 tiles (ML-KEM-512)

This note is for the tile negotiation: what each tile budget buys, measured where possible. Numbers come
from `python sim/arch_explore.py` and from the RTL in `sim/arch_explore_rtl/`. Each one is **measured**
(RTL, synthesis, FPGA), **cited** or an **estimate**. The setting is the TT demo board: RP2350 at 150 MHz,
chip at 50 MHz, every bit moved over the pins.

The budget for synthesized logic is about **32k µm² for 4 tiles (2×2)** and **63k µm² for 8 tiles (4×2)**.
That's an estimate: our 2×2 harden needed 1.6× the synthesized area once placed, at up to ~70 % density.

## Where ML-KEM-512 spends its time on the RP2350 alone

| | Total | SHA-3 / SHAKE | NTT, basemul | Rest |
|---|---|---|---|---|
| keygen | 2.62 ms | 76 % | 8 % | 17 % |
| encaps | 2.61 ms | 73 % | 10 % | 17 % |
| decaps | 2.85 ms | 67 % | 14 % | 19 % |

So an infinitely fast NTT unit gives at most 1.08–1.16×, and an infinitely fast hashing unit at most
3.0–4.1× (Amdahl).

## 4 tiles (2×2), what we have

| Design | Area | NTT call | basemul call | Whole ML-KEM-512 |
|---|---|---|---|---|
| team chip on `main` (full-rate multiplier, started every 3rd clock) | 22.9k (measured) | 53.9 µs | 38.6 µs | 0.86× |
| **+ full-rate schedule** (`spec-changes/01`) | same | 53.9 µs | **13.0 µs** | **0.92×** |
| RP2350 software, for comparison | – | 39.9 µs | 10.8 µs | 1.00× |

Nothing for hashing fits in 4 tiles at a useful speed (next section).

## 8 tiles (4×2), what more tiles could buy

| Design | Area | Effect | Whole ML-KEM-512 |
|---|---|---|---|
| team chip + full-rate schedule + **block engine (B3)**: 2–3 buffers of 16 coefficients, I/O overlapped with compute | ~45–50k (estimate) | NTT ~18–20 µs instead of 53.9 µs, **2× faster than RP2350 software** | ~1.0–1.05× |
| hashing engine | – | no fast-enough Keccak fits (next section) | – |
| polynomial cache (one full polynomial on chip) | +60–80k (estimate) | doesn't fit next to the NTT chip | – |

The honest pitch for 8 tiles is the block engine. It makes the chip's own NTT clearly faster than the
RP2350 (≈ 2×), and it enables in-hardware shuffling (an LFSR permutes butterflies inside a block; already
in the model as design B). ML-KEM as a whole barely moves, because hashing is about ¾ of the time.

## Hashing engines: is there a fast-enough one that fits?

To beat the RP2350 (about 74 µs per Keccak-f[1600] permutation) at 50 MHz, a core needs fewer than ~3,700
clocks per permutation. To reach about 1.7× overall, it needs about 1,300–1,500.

| Keccak-f[1600] design | Area | Clocks / perm. | vs RP2350 per perm. | Fits 8 tiles? |
|---|---|---|---|---|
| Pessl & Hutter, CHES 2013 (smallest full-state, latch memory) | 5.5k GE (~21k µm², estimate) | ~15,000 | **4× slower** | yes |
| Keccak team, compact (implementation overview) | 9.3k GE (~35k µm², estimate) | 5,160 | **1.4× slower** | yes |
| Kavun & Yalçın, RFIDSec 2010 | 20.8k GE (~78k µm², estimate) | 1,200 | 3× faster | no |
| **ours, lane-serial, flip-flop state** | **151k µm² (measured)** | **1,346 (measured)** | 2.7× faster | no (19 tiles) |
| **ours, lane-serial, latch state** | **99k µm² (measured)** | **1,346 (measured)** | 2.7× faster | no (13 tiles) |
| ours, latch state + clock-gated registers | ~88k µm² (estimate) | 1,346 | 2.7× faster | no (~11 tiles) |
| 1 round per clock | 145k µm² (measured) | 24 | 100× faster | no (18 tiles) |

GE → µm² uses a sky130 NAND2 (3.75 µm²). It's a rough conversion across libraries.

**Result:**
- Every Keccak core that fits in 8 tiles is slower than the RP2350's own software.
- Every core faster than the RP2350 needs at least ~11 tiles.
- Spending more clock cycles saves almost no area, because the area is the 1,600-bit state and its access
  paths, not the round logic.
- A hashing speedup needs Tiny Tapeout's 8×2 (16 tiles) or an SRAM macro for the state.

## The 3× multiplier speedup: what happened to it

- **`main` already has the full-rate multiplier** (Spec 2, Oct 17): 1 product per clock, latency 3. Its
  pure calculation time for one NTT would be 896 products = **17.9 µs**.
- **`main` doesn't run at that speed.** Each butterfly's result (2 coefficients = 3 bytes) has to leave on
  the 8 output pins, which takes 3 clocks. Control therefore starts the multiplier only every 3rd clock,
  and an NTT takes 2,688 clocks = **53.9 µs**. The multiplier idles two thirds of the time.
- **Still up for grabs without area:** basemul and scale aren't pin-limited. Spec change 1 lets them use
  the full rate: basemul 15 → 5 clocks per piece (3×), scale 6 → 3 per pair (2×).
- **Reaching ~18 µs for the NTT** means not sending every layer's results over the pins. The block engine
  keeps 16 coefficients on chip for 3–4 layers. With overlapped buffers its NTT takes about 900–950 clocks
  (≈ 18–19 µs). That needs about +20–25k µm², so it doesn't fit in 4 tiles next to the current chip; it
  fits in 8.

Chip part of one ML-KEM-512 exchange (10 NTT, 7 inverse NTT, 18 basemul, 7 scale), silicon at 50 MHz,
transfers included:

| | Time |
|---|---|
| RP2350 software | 0.85 ms |
| team chip on `main` | 1.72 ms |
| + full-rate schedule (4 tiles) | 1.21 ms |
| + block engine (8 tiles, estimate) | ~0.61 ms |

## Sources

- P. Pessl, M. Hutter, "Pushing the Limits of SHA-3 Hardware Implementations to Fit on RFID", CHES 2013,
  https://eprint.iacr.org/2013/439
- G. Bertoni, J. Daemen, M. Peeters, G. Van Assche, R. Van Keer, "Keccak implementation
  overview" v3.2, https://keccak.team/files/Keccak-implementation-3.2.pdf
- E. B. Kavun, T. Yalçın, "A Lightweight Implementation of Keccak Hash Function for Radio-Frequency
  Identification Applications", RFIDSec 2010, https://link.springer.com/chapter/10.1007/978-3-642-16822-2_20
- RP2350 software cost: pqm4 benchmarks (m4fspeed) and ePrint 2022/112, see `sim/config.py`.
