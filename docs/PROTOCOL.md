# NTT coprocessor pin protocol

> **Status: APPROVED 2026-10-17.** The RTL must match these latency constants **cycle-exactly**. Every constant lives in [`sim/protocol.py`](../sim/protocol.py);
> change it there, and the models, host, report and tests all follow.

## Pins

| Pins | Dir | Meaning |
|---|---|---|
| `ui_in[7:0]`, `uio_in[3:0]` | in | `din[11:0] = {uio_in[3:0], ui_in}` |
| `uio_in[4]` | in | `valid`: this clock carries a word |
| `uio_in[5]` | in | `sof`: start of frame |
| `uio_in[7:6]` | in | `op`: 00 CT (NTT), 01 GS (INTT), 10 basemul, 11 scale |
| `uo_out[7:0]` | out | result bytes, ByteEncode12: `b0 = v0[7:0]`, `b1 = {v1[3:0], v0[11:8]}`, `b2 = v1[11:4]` |
| `uio_out`, `uio_oe` | out | always `0x00` (all bidirectional pins are inputs) |

## Cycle convention

In cycle `t` the host drives the inputs and samples `uo_out`; then the rising edge happens.
All outputs are registered, so `uo_out` in cycle `t` depends only on inputs from earlier cycles.
When no result byte is due, `uo_out = 0x00`. There is no output-valid pin and no back-pressure.
The host knows from the constants below exactly which cycles carry result bytes.
This is the same convention cocotb and the Tang Nano rig use.

## Stream transactions (design A; design B in stream mode)

| op | words in (consecutive clocks) | result pair |
|---|---|---|
| CT | a, b | a + ζb, a − ζb |
| GS | a, b | a + b, ζ(b − a) |
| scale | x0, x1 | 3303·x0, 3303·x1 |
| basemul | a0, a1, b0, b1 | a0b0 + (a1b1)γ, a0b1 + a1b0 |

- The words of one transaction go on **consecutive** clocks with `valid = 1`.
- If a transaction's first word is in cycle `t0`, its 3 result bytes appear in cycles
  `t0 + LAT`, `t0 + LAT + 1` and `t0 + LAT + 2`.
- The next transaction may start at `t0 + PERIOD` at the earliest. Between transactions, `valid = 0`.

| op | serial multiplier: PERIOD / LAT | parallel multiplier: PERIOD / LAT |
|---|---|---|
| CT, GS | 3 / 8 | 3 / 6 |
| scale | 6 / 10 | 3 / 6 |
| basemul | 15 / 22 | 5 / 12 |

PERIOD follows from the multiplier: the serial one takes 3 clocks per product and the parallel one takes 1.
The output pins can carry at most one pair every 3 clocks, so PERIOD is never below 3.
LAT is a proposal: each value is the depth of a straightforward pipeline (worked out below) plus about 1 clock of margin.
The RTL can always add delay registers to reach a larger LAT. It can't go below one.

**Counters (design A):**
- `sof = 1` on a frame's first word resets the layer, butterfly and basemul-pair counters.
  `op` must stay the same for the whole frame.
- CT/GS frames carry 896 butterflies in canonical FIPS 203 order. The twiddle is
  `ZETAS[a_zidx_fwd(layer, n)]` or `ZETAS[a_zidx_inv(layer, n)]`.
- Basemul frames carry 128 pairs, with `γ_i = basemul_gamma(i)`.
- Scale frames carry 128 pairs.

**Clocks per polynomial:**

| | A, serial | A, parallel |
|---|---|---|
| NTT / INTT | 896 × 3 + 8 = **2,696** | 2,694 |
| scale | 127 × 6 + 13 = 775 | 390 |
| basemul | 127 × 15 + 25 = 1,930 | 650 |

**Host-side shuffle (design A):** the host may permute butterflies within a run that shares a
twiddle. With shuffle on, it waits a fixed LAT clocks after each layer, which adds 48 clocks per NTT.
Otherwise the next layer's first butterfly might need a result that is still in flight, and the
resulting stall would depend on the permutation.

## Design B

Every frame starts with a **header word** (`valid = 1`, `sof = 1`):

| Field | Bits |
|---|---|
| pass (0 fwd strided, 1 fwd contiguous, 2 inv contiguous, 3 inv strided) | `din[1:0]` |
| block mode | `din[2]` |
| block index r or b | `din[6:3]` |
| shuffle enable | `din[7]` |
| reserved, must be 0 | `din[11:8]` |

**Stream mode (`din[2] = 0`):** the header resets the counters and latches `op` from the op pins.
Design A's transactions follow, without `sof`, using the same table above.

**Block mode (`din[2] = 1`):**

| Cycle | What |
|---|---|
| `h` | header |
| `h+1 … h+16` | 16 data words, local index 0..15 in gather order (strided: `r + 16m`; contiguous: `16b + m`) |
| `h+17 … h+16+C` | compute, fixed length, the same with shuffle on or off |
| `h+17+C … h+40+C` | 24 result bytes = local pairs (0,1), (2,3), …, (14,15), ByteEncode12 |
| `≥ h+41+C` | next header |

`C = 3·nbf + 3` (serial) or `nbf + 3` (parallel), where `nbf = 32` for passes 0 and 3 (4 local layers) and
`nbf = 24` for passes 1 and 2 (3 layers). The `+3` drains the PE pipeline.

| | B1 (serial) | B2 (parallel) |
|---|---|---|
| NTT / INTT (32 blocks) | 16 × (140 + 116) = **4,096** | 16 × (76 + 68) = **2,304** |
| scale, basemul (stream mode) | as A + 1 header clock | as A + 1 header clock |

The handoff's figures (3,968 and 2,176) count `16 in + compute + 24 out` per block. The difference
of 128 clocks is 32 header clocks plus 32 × 3 drain clocks.

**Shuffle:** a free-running 16-bit Galois LFSR (taps `0xB400`, reset value `0xACE1`) advances every clock.
At the start of each local layer the chip takes `m = lfsr[2:0]` and `r = lfsr[5:3]`, and runs
butterfly `k' = ((k ^ m) + r) mod 8` in slot `k`. That gives 64 of the 8! possible orders per layer.
The butterflies of a layer are independent, so the results are unchanged.
This exact rule is a proposal too; it doesn't affect pin behaviour.

## Pipeline sketches behind the LAT values (serial multiplier)

- **CT:** a is latched at `t0` and b at `t0+1`. The multiplier's three digits run at `t0+2..4`.
  Barrett is registered at `t0+5`, add/sub and the packer at `t0+6`, so byte 0 is visible at `t0+7`.
  Proposed LAT 8.
- **scale:** x0's product runs at `t0+1..3` and x1's at `t0+4..6`. Barrett is registered at `t0+7` and the
  packer at `t0+8`, so byte 0 is visible at `t0+9`. Proposed LAT 10.
- **basemul:** five products on one multiplier, in the order a1b1, a0b0, (a1b1)γ, a0b1, a1b0.
  They finish by `t0+18`, then Barrett, add and pack take the result to `t0+21`. Proposed LAT 22.

## Protocol violations

The models (`sim/chip_a.py`, `sim/chip_b.py`) raise `ProtocolError` on any of these:
- a transaction that starts early
- a gap inside a transaction
- `op` changing without `sof`
- data before a header (design B)
- more than 896 butterflies without `sof`
- a nonzero reserved header field
- an output collision

On real silicon, any of these produces undefined results.
