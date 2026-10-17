# NTT coprocessor pin protocol

This document follows the team specs (Spec 1–5 in `ref-docs/`, Oct 17 2026). It also serves as
Spec 3's `schedule.md` and `host_timing.md`: the input schedule per mode and the output delays D,
**measured on the RTL in `src/`**. Every number lives in [`sim/protocol.py`](../sim/protocol.py)
(Spec 1's `timing.py`). The cocotb tests check the RTL against those numbers clock by clock.

## Pins (Spec 5)

| Pins | Dir | Meaning |
|---|---|---|
| `ui_in[7:0]`, `uio_in[3:0]` | in | coefficient `{uio_in[3:0], ui_in}`, 0..3328 |
| `uio_in[4]` | in | `valid` |
| `uio_in[5]` | in | `sof`: together with valid, the first coefficient of a job |
| `uio_in[7:6]` | in | `op`: 00 forward NTT, 01 inverse NTT, 10 basemul, 11 scale. Read on the sof clock only |
| `uo_out[7:0]` | out | result bytes, ByteEncode12: `r0[7:0]`, `{r1[3:0], r0[11:8]}`, `r1[11:4]` |
| `uio_out`, `uio_oe` | out | always `0x00` |

**Cycle convention:** in clock `t` the host drives the pins and samples `uo_out`, then the rising edge
happens. `uo_out` is a register, so it depends only on earlier clocks. It reads `0x00` whenever no result
byte is due. There's no output-valid flag, so the host samples at the fixed delays below.

## Jobs (Spec 3)

- A clock with `valid` and `sof` both high starts a job. `op` is latched and all counters reset, and
  that coefficient is the job's first input.
- The job ends by itself after its last input. Further valid words are ignored until the next sof,
  and so are valid words while no job is running.
- **Every sof flushes:** anything still in flight is dropped, and `uo_out` reads 0 from 2 clocks after
  the sof clock. So the host must start a job only after the previous job's last result byte.

| op | Mode | Inputs | Unit (inputs → result pair) | Pairs out |
|---|---|---|---|---|
| 00 | Forward NTT | 1792 | b = f[j+len], a = f[j] → (a + bζ, a − bζ) | 896 |
| 01 | Inverse NTT | 1792 | b = f[j+len], a = f[j] → (a + b, (b − a)ζ) | 896 |
| 10 | Basemul | 512 | g1, f1, g0, f0 → (c0, c1) | 128 |
| 11 | Scale | 256 | c, c′ → (scaled c, scaled c′) | 128 |

Butterflies come in canonical FIPS 203 order: len = 128, 64, …, 2 forward and len = 2, …, 128 inverse.
The chip derives every twiddle and γ from its counters.

## Schedule and output delay D (measured on the RTL)

Offsets are clocks from a unit's first input. Clocks with `valid` low between the listed offsets are required.

| Mode | Input offsets | Period (next unit at ≥) | **D**: first result byte at | Bytes at |
|---|---|---|---|---|
| Forward | b @0, a @1 | 3 | **6** | +6, +7, +8 |
| Inverse | b @0, a @1 | 3 | **7** | +7, +8, +9 |
| Basemul | g1 @0, f1 @1, g0 @2, f0 @3 | 15 | **20** | +20, +21, +22 |
| Scale | c @0, c′ @3 | 6 (3 per coefficient) | **9** | +9, +10, +11 |

**Where D comes from**, in clocks: input capture 1, `modq_mul` 4 (`L_MULT`), adders 0 (combinational),
packer 1, plus the control alignment below.

| Mode | Multiplier starts (pin offset) | Pair ready | Notes |
|---|---|---|---|
| Forward | b·ζ′ @1 | @5 | a waits in an operand register; Post ± is combinational |
| Inverse | (b−a)·ζ′ @2 | @6 | needs both inputs first; a+b goes through a 2-register bypass |
| Basemul | f1g1 @2, f0g0 @5, m1·γ′ @8 (loop-back), f0g1 @11, f1g0 @14 | @19 | an independent pass is interleaved because L_MULT = 4 > 3 |
| Scale | c·1441 @1, c′·1441 @4 | @8 | the first result is held as r0 |

The handoff assumed D = 5 (forward) and 7 (inverse). Inverse matches. Forward is 6 because the
multiplier starts on the clock after b is captured and takes 4 clocks. Reaching 5 would need
`L_MULT = 3`, with the reduction and Post ± squeezed into one clock.

**Clocks per job,** with continuous streaming: forward/inverse 895 × 3 + D + 3 (2,694 / 2,695),
basemul 127 × 15 + 23 = 1,928, scale 127 × 6 + 12 = 774. The host model streams NTT layers back to
back without stalls; no layer needs a result that's still in flight. With host-side shuffling it adds a
fixed D-clock gap after each layer.

## What the output bytes carry (K-RED, Spec 2/3)

`modq_mul` returns 169·a·b mod q. Twiddles are stored as ζ·169⁻¹, and the scale constant is
1441 = 3303·169⁻².

| Mode | Pins show |
|---|---|
| Forward, inverse | the plain FIPS 203 result |
| Basemul | 169 × the plain basemul |
| Scale | c · 3303 · 169⁻¹ |

The full flow (forward, basemul, inverse, scale) is therefore plain.
**ML-KEM note for the team:** KeyGen's `t̂ = Â∘ŝ + ê` uses the basemul sum *without* inverse NTT and
scale, so the host must multiply it by 169⁻¹ = 2285 (k polynomials, 256 multiplications each). Encaps
and decaps need no correction. `model/mlkem.py` does this automatically for any backend with `factor = 169`.

## Experimental: design B block mode

`sim/chip_b.py` keeps the handoff's 16-coefficient block engine as a pin-level model, for a possible
bigger tile budget. It isn't in the team plan and has no RTL. Its header-word format and timing are in
`sim/protocol.py`.
