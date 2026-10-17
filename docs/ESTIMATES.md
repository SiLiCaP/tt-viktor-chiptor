# How the silicon estimate is made, and how the chip differs from the FPGA

For the team and for anyone who quotes a speed number. The chip is not back from the fab, so every timing
for "RP2350 + our chip on the Tiny Tapeout board" is a prediction. This page explains how each part of it is
obtained and how sure we are of it. It also lists every way the FPGA stand-ins differ from the real chip.
Code: `sim/perf_model.py`, `sim/config.py`, `tools/rp_log.py`; the firmware's log is `chipathon-2026
rp2350/core/oplog.c`.

## 1. The prediction in one line

```
time of a chip call = RP2350 CPU work (build words + unpack + per-call work)
                    + transfer set-up (DMA, PIO)
                    + chip clocks / chip clock frequency
```

A whole ML-KEM operation adds the RP2350's work outside the chip calls (hashing, sampling, encoding), which
comes from cited cycle counts. The parts:

| Part | Where it comes from | How sure |
|---|---|---|
| **Chip clocks per call** | the team's `test/timing.py`: forward NTT 2,751, inverse 2,765, basemul 655, scale 394, layer by layer as the firmware sends them | **exact**: the same counts on RTL, gate level, the FPGA and in the C harness |
| **Chip clock** | the lowest of: the 50 MHz timing target, the I/O limit (assumed 50 MHz through the TT mux and pads), the PIO limit (75 MHz at a 150 MHz RP2350), and the STA (53.8 MHz worst case, measured on the team chip at acff283) | 50 MHz is the design target, closed at the slow corner. The pad path is an **assumption** until silicon |
| **RP2350 CPU work per call** | `sim/config.py` `fw_*`: per input coefficient, per chip clock, per result pair, per butterfly, per batch, per call | **estimated** from the firmware's compiled loops, until the rig measures it. Then **measured** (`perf/rp_coeffs.json`) |
| **Transfer set-up per batch** | same, `fw_batch_cyc` | estimated, then measured |
| **RP2350 work outside the chip calls** | pqm4 cycle counts (Cortex-M4), minus the cited cost of the offloaded NTT calls (ePrint 2022/112); Cortex-M33 assumed equal | **cited**, with one assumption |

## 2. Why the RP2350's own work is now the main unknown

Until Oct 18 the model assumed an optimized firmware: about 12 CPU cycles per butterfly, overlapped with the
streaming. The firmware that actually exists (`rp2350/core/ntt_chip.c`) is written for clarity. Per batch it:
1. clears and fills a word buffer;
2. streams it;
3. waits;
4. unpacks the results.

The steps run one after the other. Compiled for the Cortex-M33 (arm-none-eabi-gcc 14.2 `-O2`), its inner
loops cost:

| Loop | Instructions | Estimated cycles |
|---|---|---|
| build one input word (`run_units`) | 17 per input coefficient | 22 |
| clear the word buffer (`memset`) | – | ~1 per chip clock |
| unpack one result pair (+ `unpack_pair`) | 22 + 12 | 45 |
| NTT gather and scatter (`ntt_job`) | 6 + 6 per butterfly | 18 |
| per batch: DMA set-up, 64-bit timeout division, polling, log | – | ~500 |
| per call: two 512-byte copies, log | – | ~400 |

For one NTT layer that is about 14,000 CPU cycles (95 µs at 150 MHz). The chip needs 393 clocks for the same
layer (7.9 µs at 50 MHz). **As written, the firmware is CPU-bound by about 10×.** Per call at 50 MHz:

| Call | Chip streaming | Firmware as written (**estimate**) | Optimized firmware (**what-if**) | RP2350 software (cited) |
|---|---|---|---|---|
| forward NTT | 55 µs | 739 µs | 75 µs | 40 µs |
| inverse NTT | 55 µs | 739 µs | 75 µs | 37 µs |
| basemul | 13 µs | 137 µs | 17 µs | 11 µs |
| scale | 8 µs | 93 µs | 11 µs | (inside iNTT) |

One ML-KEM-512 key exchange (keygen + encaps + decaps):

| System | Time | vs RP2350 alone |
|---|---|---|
| RP2350 alone (cited) | 8.08 ms | 1.00× |
| RP2350 + chip, firmware as written (**estimate**) | 22.9 ms | 0.35× |
| RP2350 + chip, optimized firmware, 1 core (**what-if**) | 8.88 ms | 0.91× |
| RP2350 + chip, optimized firmware, 2 cores (**what-if**) | 8.57 ms | 0.94× |

These numbers come from `python3 sim/arch_explore.py`, which reruns them from the current coefficients.
The firmware-as-written row is the one the rig will turn from an estimate into a measurement. It replaces the
earlier 0.86× figure, which assumed the optimized firmware and the old schedule. **Optimizing the firmware's
packing is now the biggest lever on the system's speed.** Precomputed index tables, building the next batch
while the current one streams, and unpacking with word loads would bring it toward the what-if rows.

## 3. How the rig measures it

**The precise simulation needs both boards: the Pico 2 W and the Tang Nano, wired together**
([PICO_TANG_RIG.md](PICO_TANG_RIG.md)).

- **The firmware logs every batch and call** in CPU cycles of the RP2350's own counter (`log`, `log csv`,
  `predict <hz>`, `bench`). Each record splits into:
  - `prep`: building the words;
  - `run`: the transport;
  - `conv`: the rig's word spreading, which the demo board doesn't need;
  - `post`: unpacking;
  - the call's remaining work.
- **`tools/rp_log.py capture` turns the log into the model's coefficients:**
  - it runs `bench` on the Pico and reads the log;
  - it fits the costs per coefficient, per clock, per pair, per butterfly, per batch and per call;
  - it saves them to `perf/rp_coeffs.json`.

  `sim/perf_model.py` then uses them everywhere: the website, `tools/perf.py`, `sim/arch_explore.py`,
  `sim/sha3_options.py`. Their status changes from "ESTIMATE" to "measured: RP2350 timing log, <file>".
- **The prediction takes from the rig only what transfers to the demo board:**
  - It keeps the measured CPU work. It's the same RP2350 core at the same clock running the same compiled code.
  - It drops `conv`.
  - It recomputes the streaming as exact clocks ÷ the target clock. The rig's own clock is slower because of
    the wires, so its streaming time is not used.
  - The DMA/PIO set-up and finish time measured per batch is kept.

What the rig can't tell us:
- **Whether DMA keeps up at 50 MHz.** It must move one 16-bit word in and one byte out per chip clock. The rig
  runs at a lower clock, so a DMA bottleneck at 50 MHz would only show up on the demo board. If it happens,
  the PIO stalls and the chip simply runs slower; results stay correct.
- **The real pad and clock-insertion delays.** `cal` and `sweep` will find them on silicon.

Without the Pico (Tang Nano over USB only), the FPGA still checks every byte. But its timing is the USB-UART,
about 1 Mbaud, which says nothing about the RP2350's costs. That's why those runs are marked as FPGA/USB and
never feed the coefficients.

## 4. How the planned chip differs from the FPGA

| Aspect | Tiny Tapeout chip (planned) | Tang Nano 20K stand-in |
|---|---|---|
| **Logic** | `tt_um_NTT_Core`, sky130 standard cells after LibreLane (synthesis, placement, clock tree, buffering) | **the same gate netlist**: each sky130 cell rebuilt from its liberty logic function, mapped to LUTs and flip-flops. Function is identical gate for gate |
| **What a pass proves** | – | the gates compute the right bytes on the right clock. It does **not** prove sky130 timing; that is the STA's job |
| **Timing** | 50 MHz target; STA +1.41 ns at the slow corner (≈ 53.8 MHz), +10.5 ns typical (≈ 105 MHz) | FPGA routing delays have nothing to do with sky130. The gate netlist meets about 87–99 MHz inside the FPGA; the rig's wires set its usable clock |
| **Clock path** | TT clock pad → mux → project, up to ~10 ns insertion delay | Pico GP21 → wire → global clock pin 77 → global buffer: small, different skew |
| **I/O** | 8 in + 8 out + 8 bidirectional pads behind the TT mux; `ena` from the mux | header pins straight to the design; `ena` tied high; `uio` wired as inputs only (this chip never drives them) |
| **Host connection** | demo board traces, a few cm, RP2350B | jumper wires 2–4× longer, RP2350A (same cores, PIO, DMA; fewer pins, so the input window wraps) |
| **Reset** | `rst_n` from the RP2350 through the mux | `rst_n` from the Pico, pulled down at the FPGA |
| **Area** | 31,799 µm² synthesized, 38,128 µm² placed (52 % of 2×2) | ~3,400 LUTs and 790 flip-flops of 20,736 / 15,552 (the UART player included) |
| **Power, side channels** | real CMOS, real leakage | not representative at all; the masking result (pins) holds, nothing else does |
| **Max speed of the NTT itself** | pin-bound: 3 clocks per butterfly at up to ~50 MHz | the same clocks, at whatever the wires allow |

In short:
- **Function:** the FPGA rig shows the chip is right.
- **Timing:** the STA shows the chip is fast enough.
- **System time:** the Pico + Tang rig shows what the RP2350 costs around each call.

Combined with the exact clock counts, that gives the silicon estimate.
