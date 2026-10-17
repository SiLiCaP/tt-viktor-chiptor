# Handoff: ML-KEM NTT coprocessor, Chipathon 2026 (state on Oct 18, 2026)

For whoever picks this up next: a teammate, or Viktor in a new session. It says what exists, what has
been proven and how, how to rerun everything, and what is still open. Numbers are tagged **measured**,
**cited** or **estimate**, as in the other docs.

## 1. In one paragraph

The team is taping out an NTT coprocessor for ML-KEM-512 (FIPS 203) on Tiny Tapeout ttsky26d in 4 tiles
(2×2): `tt_um_NTT_Core` in [chipathon-2026](https://github.com/SiLiCaP/chipathon-2026). This repo,
`tt-viktor-chiptor`, is Viktor's exploration and verification workbench around that chip. It holds:
- a FIPS 203 golden model and a cycle-exact model of the chip's pins;
- an earlier version of the chip (`src/`, `tt_um_ntt_engine`);
- a Tang Nano 20K FPGA rig that now runs the **team chip's hardened sky130 gate netlist**;
- a demo website, a performance model, and architecture studies (tiles, SHA-3).

The RP2350 firmware that drives the real chip lives in the team repo (`rp2350/`). The chip is
functionally proven up to gate level on the FPGA. It is not faster than the RP2350's own software, and
the docs explain why: the pins, SHA-3, and now mainly the firmware's own packing work.

**New on Oct 18:**
- **Team design:** the team adopted the full-rate schedule and closed timing at 50 MHz (`acff283`).
- **Pico 2 W + Tang Nano rig:** the same RP2350 drives the chip's gate netlist over 26 wires
  ([PICO_TANG_RIG.md](PICO_TANG_RIG.md)).
- **Timing log:** the firmware times every chip batch and call, and `tools/rp_log.py` turns that log into
  measured costs for the silicon prediction ([ESTIMATES.md](ESTIMATES.md)).
- **Status:** all of this is coded and checked in simulation. Neither board was connected, so none of it has
  run on hardware.

## 2. Two repositories

| Repo | What lives there | Who changes it |
|---|---|---|
| `chipathon-2026` (team) | the tapeout design `src/` (`tt_um_NTT_Core`), specs 1–5, `docs/host_timing.md`, team tests `test/`, **RP2350 firmware `rp2350/`**, `docs/architecture_options.md`, `docs/sha3_report.md` | the team; change it only when asked |
| `tt-viktor-chiptor` (this) | models, FPGA rig, demo website, performance and architecture tools, the earlier RTL `src/` | Viktor |

The two are checked out side by side: `~/Documents/Projects/Chipathon2026/{chipathon-2026,tt-viktor-chiptor}`.
Several tools here find the team repo at `../chipathon-2026`. Push access over SSH works for both.

**The team specs govern** (`ref-docs/Spec 1-5`, design A, K-RED multiplier). They override the older
handoffs in `ref-docs/HANDOFF_*.md`. The team target is **ML-KEM-512**: every default, demo and estimate
uses 512.

## 3. What is proven

| Level | What | Result | How to rerun |
|---|---|---|---|
| Model | FIPS 203 ML-KEM-512/768 with chip backends | byte-identical to the reference | `python3 -m pytest -q test/py` (190 tests) |
| Model | team chip arithmetic (`NTT_CHIP=team`) vs the team's `test/ntt_ref.py` | equal | `test/py/test_team_model.py` |
| Team RTL | team cocotb suite on `main` (91eb006) | 14/14 pass | `make -C ../chipathon-2026/test` |
| Own RTL | `src/` cocotb replay of ML-KEM traces | 6/6 pass | `make -C test` (sets `NTT_CHIP=own`) |
| Team chip, hardened (`acff283`) | TT flow (LibreLane), 2×2 | LVS/DRC clean, 0 antenna, **50 MHz met at the slow corner** (+1.41 ns) | `make -C fpga netlist` |
| FPGA, team **gate netlist** (`91eb006`, the previous design) | 3 full ML-KEM-512 exchanges, every output byte checked | PASS (85,927 clocks each) | `make -C fpga prog && python3 host/test_ntt.py --seeds 3` |
| FPGA, team RTL (`91eb006`) | same | PASS | `make -C fpga prog GL=0`, same test |
| FPGA, team gate netlist + RTL (`91eb006`) | team C harness (`rp2350/`): known answers, Spec 1 demo, fuzz, k = 2 matvec | PASS, clocks equal `host_timing.md` | `../chipathon-2026/rp2350/pc/ntt_host --port /dev/ttyUSB1 all` |
| FPGA, `acff283` gate netlist | bitstreams for USB and for the rig build; **not yet run on the board** | built | the same commands |
| Rig FPGA top (`acff283` RTL) | a polynomial multiply driven through the header pins like the PIO | PASS in cocotb, every byte | `make -C fpga/sim_pico` |
| Model vs team timing (`acff283`) | Python cycle model reads `../chipathon-2026/test/timing.py`; C harness vs software chip | PASS, clocks 2,751 / 2,765 / 655 / 394 | `pytest test/py`, `make -C ../chipathon-2026/rp2350/pc test` |
| Timing-log fitter | a synthetic log fits back to its own costs | PASS | `test/py/test_rp_log.py` |
| **Pico 2 W + Tang Nano rig** | the whole chain over wires | **not run** (boards not connected) | [PICO_TANG_RIG.md](PICO_TANG_RIG.md), "Bring-up" |
| RP2350 firmware | builds (pico-sdk 2.1.1); CI `rp2350` workflow green, UF2 as artifact | builds | `cmake -S rp2350 -B rp2350/build ...` (see its README) |
| **RP2350 on a real demo board** | PIO/DMA transport, mux select, USB | **not run** (no board here) | `rp2350/README.md`, "Bring-up on silicon" |

## 4. Quick start on Viktor's machine

```bash
cd ~/Documents/Projects/Chipathon2026/tt-viktor-chiptor
source ~/tools/oss-cad-suite/environment          # yosys, nextpnr, iverilog, cocotb (Python 3.11)
make -C fpga prog                                 # team chip, gate netlist, onto the Tang Nano (SRAM)
python3 host/tt_emu.py --ping                     # /dev/ttyUSB1: magic TTE1
python3 host/test_ntt.py --seeds 3                # 3 ML-KEM-512 exchanges, byte-checked
python3 host/showcase.py                          # demo website, http://localhost:8080 (--sim without board)
```

The FPGA bitstream lives in SRAM: run `make -C fpga prog` again after every replug.

Tools (all in `~/tools`, nothing installed system-wide):

| Tool | Path | Notes |
|---|---|---|
| OSS CAD Suite | `oss-cad-suite` | source its `environment`; its Python 3.11 has cocotb 2.1 |
| TT flow | `tt-support-tools`, `tt-venv`, `bin/docker` | `bin/docker` is a podman shim with `--security-opt label=disable` (SELinux); the PDK is in `~/.ciel` |
| RP2350 build | `arm-gnu-toolchain` (14.2), `pico-sdk` (2.1.1), `pico-tools` (prebuilt pioasm, picotool 2.1.1), `cmake-venv` (cmake, ninja) | there is **no host g++** on this machine, so pioasm and picotool are prebuilt |
| References | `ref/tt-micropython-firmware` | demo board pin map and mux protocol |

## 5. Map of this repo

| Path | What |
|---|---|
| `model/mlkem_ntt_model.py` | golden NTT model (FIPS 203 Algorithms 9–12) |
| `model/mlkem.py` | ML-KEM-512/768 (FIPS 203) with pluggable backends: reference, counting, timing, chip |
| `model/chip_arith.py` | chip arithmetic: `NTT_CHIP=team` (3 K-RED rounds, factor 2197, **default**) or `own` (2 rounds, 169) |
| `model/packet.py` | demo message encryption (SHAKE256 keystream + HMAC-SHA3-256) |
| `sim/` | cycle-exact pin model (`chip_a.py`, `protocol.py`, `pins.py`, `host.py`) |
| `sim/` | stimulus export (`export.py`) |
| `sim/` | performance model (`perf_model.py`, `config.py`: every coefficient with its source) |
| `sim/` | studies: `arch_explore.py` (tiles, Keccak), `sha3_options.py` |
| `sim/arch_explore_rtl/` | verified exploration RTL: lane-serial Keccak (flip-flop and latch), parallel multiplier |
| `src/` | the earlier chip `tt_um_ntt_engine` (2 K-RED rounds); `info.yaml` here builds it |
| `test/test.py`, `test/py/` | cocotb tests of `src/`; Python tests of models and simulation |
| `fpga/` | Tang Nano 20K rig: wrapper `tangnano20k_top.v`, `uart.v`, `Makefile`, `harden.sh`, `sky130_phys_cells.v`, `PROTOCOL.md` (TTE1) |
| `host/tt_emu.py` | PC driver for TTE1: LOAD / RUN / READ_CAP, phase timers |
| `host/board.py` | chip backend over any transport, masking, hooks |
| `host/test_ntt.py` | byte-exact board test |
| `host/showcase.py` + `.html` | the demo website (8 tabs) |
| `host/demo.py`, `host/live_demo.py` | older demos (figures in `reports/demo/`) |
| `tools/perf.py` | performance log `perf/perf_log.jsonl`, plots in `reports/perf/` |
| `tools/gen_zeta_rom.py` | generator for `src/zeta_rom.v` |
| `docs/FPGA_DEMO.md` | how to run every demo and test on the FPGA |
| `docs/ARCHITECTURE_OPTIONS.md` | what 4 and 8 tiles buy |
| `docs/PICO_TANG_RIG.md` | the Pico 2 W + Tang Nano 20K rig: wiring, safety, bring-up |
| `docs/ESTIMATES.md` | how the silicon estimate is built, and how the chip differs from the FPGA |
| `fpga/tangnano20k_pico_top.v`, `fpga/pico_rig_pins.py` | the rig's FPGA top; the one wiring table, which generates `tangnano20k_pico.cst` |
| `fpga/sim_pico/` | cocotb test of the rig top, driven like the PIO |
| `tools/rp_log.py` | the RP2350 timing log → measured firmware costs (`perf/rp_coeffs.json`) |
| `docs/spec-changes/` | proposals to the team: 01 full-rate multiplier schedule, 02 hasher engine with fit check |
| `ref-docs/` | team specs, original handoffs, the Cortex-M4 paper (ePrint 2022/112) |

## 6. The Tang Nano rig

Two ways to drive the FPGA:
- **USB (`TARGET=uart`, the default):** the PC plays the RP2350 over USB.
- **Pico 2 W rig (`TARGET=pico`):** a Pico 2 W drives the chip's pins over 26 wires
  ([PICO_TANG_RIG.md](PICO_TANG_RIG.md)). Only the rig gives the RP2350's real timing.

- **What it runs.** `make -C fpga prog` builds `DESIGN=team` with `GL=1` by default. That is the team
  chip's hardened gate netlist, taken from `fpga/build/harden/tt_um_NTT_Core/` and made with
  `make -C fpga netlist`, which hardens the team repo's committed HEAD in a copy. yosys
  `read_liberty -ignore_miss_func` rebuilds all 422 sky130 cell types from their liberty functions.
  Fillers and well taps have no logic and are stubbed in `sky130_phys_cells.v`.
  - `GL=0`: the team RTL.
  - `DESIGN=own`: `src/`; the host commands then need `NTT_CHIP=own`.
  - `GL_NETLIST=path`: a netlist from the team's GitHub GDS action.
- **Measured resources (team gate netlist, `acff283`, USB build):** 3,386 LUT4 and 789 DFF of 20,736 / 15,552.
  The chip clock is good for 70–80 MHz inside the FPGA; the USB player runs it at 13.5 MHz.
- **The chip clock is on a global buffer (BUFG).** On fabric routing its skew (1.6 ns measured) caused
  hold violations with the gate netlist.
- **Protocol** (`fpga/PROTOCOL.md`, TTE1): binary over the BL616 USB-UART at **1 Mbaud**. 1.5 and 3 Mbaud
  lose bytes. Each chip call is LOAD (2 bytes/word), RUN, READ_CAP (3 bytes/word). That is why a key
  exchange takes about 5–8 s on the rig: almost all of it is USB.
- **Every test so far passes with sample skew 0.**

## 7. Key numbers

| Number | Value | Tag, source |
|---|---|---|
| Team chip, synthesized (TT flow) | 31,799 µm², 3,064 cells | measured, local harden of `acff283` |
| Team chip, placed | 38,128 µm², 52.5 % of 2×2 | measured |
| Team chip slack at 50 MHz | +10.5 ns typical (≈ 105 MHz); **+1.41 ns at the slow corner (≈ 53.8 MHz)**, 0 setup violations; 1,242 max-slew warnings at ss 100 °C 1.60 V | measured (matches the team's own figure) |
| Same chip, plain yosys | 22,903 µm²; × 1.6 placement ratio = 36.6k, which checks out | measured; used in the tile budgets |
| Clocks per call (full rate, `acff283`) | NTT 2,751, inverse 2,765, basemul 655, scale 394; polynomial-multiply demo 9,316 | `docs/host_timing.md`; equal in the Python model and the C harness |
| One NTT on silicon at 50 MHz | chip 55 µs; with the RP2350's packing as written ~739 µs (estimate); optimized firmware ~75 µs; RP2350 software 39.9 µs | [ESTIMATES.md](ESTIMATES.md) |
| One ML-KEM-512 exchange | RP2350 alone 8.08 ms; + chip, firmware as written 22.9 ms (0.35×, estimate); optimized 8.88 ms (0.91×), 2 cores 8.57 ms (0.94×) | estimate: exact clocks + cited cycles + estimated firmware costs, until the rig measures them |
| Hashing share of ML-KEM-512 | 67–76 % (Amdahl ceiling for any NTT unit: 1.08–1.16×) | cited, pqm4 |
| Software-only speed-up | keep Â + hash on both cores: 5.50 ms, 1.47× | estimate, `sim/sha3_options.py` |
| Keccak on chip | lane-serial 1,346 clocks/permutation; 151k µm² (flip-flops) / 99k (latches) ≈ 13+ tiles → 1.73× if it fit | measured RTL + synthesis |
| Pin snooping | unmasked: 256/256 secret coefficients read off the pins; with host masking: 0/256 (2× chip calls) | measured on the FPGA |
| Constant time | 18,488 chip clocks for every keygen secret | measured |

## 8. Decisions taken, and why

- **Team spec over the older handoffs.** Viktor's instruction: the team's Spec 1–5 is the plan.
- **ML-KEM-512 everywhere.** It is the team target.
- **Multiplier latency stays the team's call.** They optimized it; the full-rate schedule is offered as
  spec change 1, not imposed.
- **`NTT_CHIP` defaults to `team`.** The FPGA and the website default to the tapeout chip. Everything that
  tests `src/` pins `own`:
  - `test/Makefile`, `test/test.py`, `test/py/conftest.py`, `tools/gen_zeta_rom.py`;
  - `sim/export.py`, only when run directly. Importing it must not change the model.
- **Gate netlist by default on the FPGA.** Viktor asked for a "direct logic gate copy" of what goes on
  the chip.
- **Clock counts stay exact in the RP2350 firmware.** DMA uses 16-bit TX and 8-bit RX, one entry per clock,
  so no padding clocks are added.
- **RP2350 firmware speaks TTE1.** The PC tools (`host/test_ntt.py`, `host/showcase.py`) then run unchanged
  against the real chip via `--port /dev/ttyACM0`.

## 9. Open items, most urgent first

1. **Wire up and run the Pico 2 W + Tang Nano rig** ([PICO_TANG_RIG.md](PICO_TANG_RIG.md)):
   - `make -C fpga prog TARGET=pico`, flash `tt_ntt_pico2w_tang.uf2`, wire the 29 jumpers;
   - then `selftest`, `sweep`, `all`, and `python3 tools/rp_log.py capture --port /dev/ttyACM0`.

   This replaces the estimated firmware costs with measured ones. Run `host/test_ntt.py` on the Tang Nano
   alone first: the `acff283` gate netlist hasn't run on the board yet.
2. **The firmware is CPU-bound, about 10×** (Spec 1 owner). Building and unpacking the words costs ~95 µs per
   NTT layer against 8 µs of chip time, so the system estimate is 0.35× with the firmware as written and
   0.91× optimized ([ESTIMATES.md](ESTIMATES.md)). Fixes, roughly in order of gain:
   - precomputed word and index tables;
   - building the next batch while the current one streams;
   - unpacking with word loads.

   The rig log will show which part dominates.
3. **RP2350 bring-up on the demo board** (team, once chips exist): `select <address>`, `selftest`, `cal`,
   `sweep`, `all`. The mux address comes from the shuttle index. Remaining: the 1,242 max-slew warnings at the
   slow corner, and `info.yaml` `clock_hz` (still 1 MHz).
4. **Tile negotiation.** 8 tiles would fit the block engine, making the chip's NTT about 2× faster than
   software (estimate). No Keccak fits in 8.
5. **Question for the TT organizers:** can a project instantiate an sky130 SRAM macro? It is the only route
   to a hashing engine in 8 tiles (`docs/sha3_report.md` in the team repo).
6. **RP2350 software speed-ups** (Spec 1 owner): keep Â between keygen and decaps, and hash on both cores.
   Estimated 1.47×; free.
7. **Name:** `tt_um_ntt_engine` in this repo is a placeholder. The team chip is `tt_um_NTT_Core`.
8. **The presentation deck and the Q&A page** are private claude.ai artifacts on Viktor's account:
   - deck: https://claude.ai/artifact/9soAp8EUmShXvjRYLANEWz
   - Q&A: https://claude.ai/artifact/RatupDmVDu3qChirmKAGZT

   They predate the gate-level switch and the Oct 18 changes. Points now out of date:
   - The FPGA runs the team chip's gate netlist, not the earlier RTL. The Q&A answer "Is the FPGA running
     the same design you're taping out?" is now "yes, its gates".
   - The chip area is 31.8k µm² synthesized and 38.1k placed in the TT flow (22.9k plain yosys).
   - Timing now closes at 50 MHz at the slow corner.
   - Basemul and scale are full rate (655 and 394 clocks).
   - The system estimate is 0.35× with the firmware as written and 0.91× optimized, not 0.86×.

   Update them only when Viktor asks.

## 10. Gotchas

- **The Tang Nano's USB bridge (BL616) can hang.** Unplug, plug back in, then `make -C fpga prog`.
  - Its console toggles with Ctrl-X Ctrl-C.
  - The udev rule must be numbered below 73 (`70-tangnano20k.rules`) for the uaccess permission to apply.
- **Only one program can own the serial port.** Stop the website before `host/test_ntt.py`. Find servers
  by port with `ss -ltnp 'sport = :8080'`; `pkill -f` can kill your own shell.
- **The TT flow can't read `/tmp`** (the podman container doesn't see it). `fpga/harden.sh` works under
  `fpga/build/`.
- **`NTT_CHIP` is read once, at import of `chip_arith`.**
  - Set it before starting Python, not inside a script after imports.
  - In a Makefile, put comments on their own line: `export X = own   # comment` puts the spaces into the
    value.
- **Verilator needs g++, which this machine lacks.** Exhaustive unit tests use Icarus, split across 28 cores.
- **Hardware results are bytes at fixed clock positions.** The chip has no valid flag, and a `0x00` means
  nothing elsewhere.
