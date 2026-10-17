# Spec change 1: use the full-rate multiplier in Control

**For:** the team (Spec owners 1–5). **Base:** `chipathon-2026` at `bb17782` (specs/, docs/schedule.md,
docs/host_timing.md, test/timing.py). **Status:** proposal. The schedule below was checked in the
cycle-accurate model (`tt-viktor-chiptor`, `sim/protocol.py` `use_full_rate()`): no protocol violations,
polynomial multiplication equals schoolbook, and 10 ML-KEM-512 runs are byte-identical to FIPS 203.

## Why

Spec 2 already adopted the full-rate K-RED multiplier (`modmul_kred`: one product per clock, latency 3,
factor 2197). Control still starts it at most once every 3 clocks, so its speed is unused. Starting it
when the operands are ready changes:

| Mode | Today | Full rate | Limited by |
|---|---|---|---|
| Forward / inverse NTT | 3 clocks / butterfly | **unchanged** | output pins: 3 bytes per butterfly |
| Basemul | 15 clocks / piece | **5 clocks / piece** | multiplier: 5 products per piece |
| Scale | 6 clocks / pair | **3 clocks / pair** | output pins: 3 bytes per pair |

Per call: basemul 1,943 → **655** clocks, scale 780 → **394** clocks (units × period + D + 3, as in
host_timing.md). For one ML-KEM-512 exchange (18 basemul + 7 scale calls) that saves about
25,700 clocks, 0.51 ms at 50 MHz. The chip part goes from 0.86× to 0.92× of the RP2350 alone.

**Area:** no change for the multiplier (already full-rate, 8,785 µm²). Control loses the 3-clock pass timer
and gains a 5-step pass sequencer. The difference is small.

## What changes, file by file

### Spec 2 (Multiplier)
No change to the block. The "Today Control starts at most once every 3 clocks" sentence becomes:
"Control starts it on consecutive clocks in basemul (5 starts per piece) and in scale."

### Spec 3 (Control) and docs/schedule.md

**Forward and inverse NTT:** no change.

**Basemul, period 15 → 5.** The host offsets stay the same (g1 @0, f1 @1, g0 @2, f0 @3); the next
piece starts at 5. Core clocks are counted as in schedule.md, where a word sent at host offset o is on
`coeff_q` at core offset o.

| Core offset | Chip does |
|---|---|
| 0 | g1 → R0, look up γ′ → `zeta_r` |
| 1 | f1 → R1 |
| 2 | g0 → R2. **Start m1 = f1 × g1** |
| 3 | f0 → R3. **Start m5 = f1 × g0** |
| 4 | **Start m4 = f0 × g1** (last use of g1) |
| 5 | **Start m2 = m1 × γ′**, with m1 taken straight from `p_out` as it arrives. The next piece's g1 → R0 and γ′ lookup happen on this clock; `zeta_r` still holds this piece's γ′ |
| 6 | **Start m3 = f0 × g0.** m5 back: acc1 ← m5 |
| 7 | m4 back: acc1 ← acc1 + m4 = **c1** |
| 8 | m2 back: acc0 ← m2 |
| 9 | m3 back: acc0 ← acc0 + m3 = **c0** |
| 10 | `pair_valid`: r0 = c0, r1 = c1 |

Notes:
- The multiplier starts on 5 consecutive clocks (2–6). The next piece's starts are 7–11, so they never collide.
- Every operand register is read for the last time before the next piece overwrites it: g1 at 4 (next
  write 5), f1 at 3 (6), g0 at 6 (7), f0 at 6 (8).
- **This order is fixed to `L_MUL` = 3**: m2 starts at exactly 2 + `L_MUL` = 5. With another latency,
  hold γ′ in its own per-piece register and re-time the passes. The "latency 2 to 6" flexibility goes
  away for basemul.
- The accumulator use changes order: c1 now loads m5 and adds m4; c0 loads m2 and adds m3.
  `modq_acc` is unchanged.

**Scale, unit = one pair, period 3.** c at host offset 0 and c′ at offset 1, then the next pair at 3.

| Core offset | Chip does |
|---|---|
| 0 | c → R0 |
| 1 | Start c × 304. c′ → R1 |
| 2 | Start c′ × 304 |
| 4 | first product back: hold as r0 |
| 5 | `pair_valid`: r0 = held, r1 = second product |

The multiplier now starts on every clock in a continuous scale stream (two starts per 3 clocks).

**Output delays (host_timing.md):**

| Constant | Today | Full rate | Formula |
|---|---|---|---|
| `D_F` | 6 | **6** | unchanged |
| `D_I` | 7 | **7** | unchanged |
| `D_B` | 20 | **12** | L_CAP + 10 + L_PACK |
| `D_S` | 9 | **7** | L_CAP + 5 + L_PACK |
| `P_B` | 15 | **5** | |
| `P_S` | 3 per coefficient (6 per pair) | **3 per pair** (c at 0, c′ at 1) | |

**Job lengths (host_timing.md):** basemul 1920 + 23 = 1,943 → 640 + 15 = **655**; scale 768 + 12 = 780 →
384 + 10 = **394**. Demo (3 NTT + basemul + scale): 10,983 → about **9,100**.

**Assertions:** `pair_valid` ≥ 3 clocks apart still holds (basemul 5, scale 3, NTT 3).

### Spec 1 (Pi harness)
- Timing constants: `P_B` 15 → 5 (the "12 if Karatsuba" note is obsolete), `D_B` → 12, `D_S` → 7.
- **Scale input order changes:** send pairs (c, c′) on consecutive clocks, one pair per 3 clocks.
  It's no longer one coefficient every 3 clocks.
- Demo expected chip clocks: 3 × 2,688 + 640 + 384 ≈ 9,090 streaming (was about 10,750).

### Spec 4 (Adders)
No module change. In the "How Control uses your modules" table, c1 becomes "ld m5, then add m4"
(was "ld m4, then add m5"). The sum is the same.

### Spec 5 (I/O)
No change. The packer sees `pair_valid` every 5 clocks in basemul and every 3 in scale. Scale output
becomes a gap-free byte stream, like the NTT modes.

### test/timing.py and the pin tests
Update `P_B`, `D_B`, `P_S`, `D_S` and the scale offsets. `test_output_delay` and `test_full_flow` then
check the new values. The stimulus generator's scale unit changes from one coefficient to a pair.
