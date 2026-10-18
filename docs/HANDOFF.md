# Handoff: ML-KEM coprocessor for Tiny Tapeout, Chipathon 2026 (state on Oct 18, 2026, evening)

For whoever picks this up next: a teammate, or Viktor in a new session. It says what exists, what is proven
and how, how to rerun everything, and what is open. Numbers are tagged **measured**, **cited**, **model** or
**estimate**.

## 1. In one paragraph

The team designs an ML-KEM-512 (FIPS 203) coprocessor for Tiny Tapeout (ttsky26d) in
[chipathon-2026](https://github.com/SiLiCaP/chipathon-2026). There are two candidate chips:

| | `main`: NTT chip | branch `sha3-only`: hash chip |
|---|---|---|
| What | `tt_um_NTT_Core`: the NTT, inverse NTT, basemul and scale | the NTT removed; a Keccak-f[1600] sponge (`keccak_ring`, K = 8) with burst squeeze and on-chip SamplePolyCBD |
| Tiles | 2×2 | 3×2 |
| Hardened | clean, 50 MHz | **clean, 50 MHz with +8.17 ns slow-corner slack** |
| Speed (model) | 0.91× the RP2350 alone at best: the NTT is pin-bound and slower than the RP2350's own | **2.54× faster** than the RP2350 alone: 8.08 → 3.18 ms per exchange |
| On hardware | gate netlist on the Tang Nano: ML-KEM-512 byte-exact | Pico 2 W + Tang Nano rig: 42/42 jobs bit-exact up to 13.5 MHz; full key exchange with all 32 hash calls on the chip |

Hashing is 57–76 % of ML-KEM's time, which is why the hash chip is the one that speeds it up. The team still
has to pick. This repo, `tt-viktor-chiptor`, is Viktor's workbench around both:
- models;
- the FPGA rig;
- the tile experiments;
- the demo;
- performance studies.

## 2. Repositories and checkouts

| Where | What | Who changes it |
|---|---|---|
| `~/Documents/Projects/Chipathon2026/chipathon-2026` (`main`) | team repo: NTT chip `src/`, specs, team tests, **RP2350 firmware `rp2350/`**, docs (incl. `docs/tile_routes.md`, `docs/sha3_only_3x2.md`) | the team; change only when asked |
| `~/tools/work/br/sha3-only` | worktree of branch **`sha3-only`**: the hash chip (`src/hash_io.v`, `src/keccak_ring.v`, `src/tt_um_NTT_Core.v`), its tests, relaxed config, `rp2350/` incl. `core/sha3_sw.c` | Viktor (made on request, Oct 18) |
| `~/tools/work/br/sha3-asic-research` etc. | worktrees of the team's research branches (`hold14.sdc`, `no_synth_small.cells` come from there) | the team |
| `~/Documents/Projects/Chipathon2026/tt-viktor-chiptor` (this) | models, FPGA rig, demo, tile experiments, profile, route model | Viktor |
| `~/tools/work/exp/<name>` | one folder per tile experiment (built by `tools/tile_exp.py`) | generated |

The team specs govern (`ref-docs/Spec 1-5`). The target is **ML-KEM-512** everywhere.

## 3. What is proven

| Level | What | Result | Rerun |
|---|---|---|---|
| Hash chip RTL (`sha3-only`) | `test/test_hash_only.py`: every SHA-3 / SHAKE at the rate edges, byte and burst squeeze, CBD η = 2 / 3 vs FIPS 203, quiet output | **4/4 at K = 8 and at K = 16**; Verilator `-Wall` clean | `cd test && make` / `HASH_K=16 make` (in the worktree) |
| Keccak core | `keccak_ring` core test at K = 2 / 4 / 8 / 16 | pass (K = 16 after the step-counter fix) | team `research/sha3` core test |
| Hash chip harden, 3×2 (K = 8 + CBD) | TT flow, relaxed recipe | **clean**: 55.5 %, 0 DRC / LVS / antenna, setup +8.17 ns slow corner, hold +0.018 ns, 3.75 mW | `python3 tools/tile_exp.py run hash_k8_3x2` |
| Tile matrix | every route at 2×2 / 3×2 | section 7 | `tools/tile_exp.py`, `tools/harden_times.py` |
| Rig wiring | Pico 2 W ↔ Tang Nano, 26 signal wires, pin-echo bitstream | **all OK at 1, 4.5, 13.5 MHz** | `python3 tools/rig_pincheck.py` |
| Hash chip on the rig | 42 jobs: 24 byte squeeze, 12 burst, 6 CBD | **42/42 at 1.04, 3.38, 6.75, 13.5 MHz** through the Pico; 42/42 over Tang USB | `python3 host/test_variant.py --port /dev/ttyACM0 --hash 8 --hash-only` |
| ML-KEM-512 on the rig | all 32 hash calls of an exchange on the chip | keys identical to pure-software FIPS 203, every call equal to hashlib, 0.35 s | `python3 host/sha3_demo.py --check` |
| Python chip model | pin-level model of the hash chip (`ChipModel` in `host/sha3_demo.py`) | passes the same 42 jobs | `python3 host/sha3_demo.py --sim --check` |
| ML-KEM-512 profile | PQClean clean on a Cortex-M33 emulator | Keccak 57.5 %, NTT family 25.6 %, rest ≤ 8 % each | `make -C tools/mlkem_profile run` |
| NTT chip (`main`, `acff283`) | TT flow 2×2 | clean, +1.41 ns slow corner | `make -C fpga netlist` |
| NTT chip on the FPGA (`91eb006` gate netlist) | 3 ML-KEM-512 exchanges, every byte | PASS | `make -C fpga prog && python3 host/test_ntt.py --seeds 3` |
| RP2350 firmware (`main` and `sha3-only`) | builds for `pico2w_tang` (pico-sdk 2.1.1) | builds; the rig firmware's TTE1 bridge is what the demo uses | `rp2350/README.md` |
| Not done | hash chip gate-level simulation, TT precheck; RP2350 firmware hash path; a real demo board | – | section 9 |

## 4. Quick start

```bash
python3 ~/Documents/Projects/Chipathon2026/tt-viktor-chiptor/host/sha3_demo.py    # the demo: http://localhost:8080
```

It loads the hash chip into the FPGA if needed. The guide is [FPGA_DEMO.md](FPGA_DEMO.md); wiring and
bring-up are in [PICO_TANG_RIG.md](PICO_TANG_RIG.md). For the other tools:

```bash
cd ~/Documents/Projects/Chipathon2026/tt-viktor-chiptor
source ~/tools/oss-cad-suite/environment             # yosys, nextpnr, iverilog, cocotb, pyserial
python3 host/test_variant.py --port /dev/ttyACM0 --hash 8 --hash-only    # 42 hash jobs on the rig
python3 tools/rig_pincheck.py --port /dev/ttyACM0 --mhz 1 5 13.5         # wiring (pin-check bitstream)
python3 tools/tile_exp.py status                     # every tile experiment and its signoff
python3 tools/harden_times.py                        # how long each harden took, by stage
python3 sim/route_model.py                           # exchange time of every route
```

Tools live in `~/tools`; nothing is installed system-wide:
- OSS CAD Suite;
- the TT flow (`tt-support-tools`, `tt-venv`, and `bin/docker`, a podman shim);
- the RP2350 build (`arm-gnu-toolchain`, `pico-sdk` 2.1.1, `pico-tools`, `cmake-venv`).

## 5. Map of this repo (new on Oct 18 in bold)

| Path | What |
|---|---|
| **`host/sha3_demo.py` + `.html`** | the demo: ML-KEM-512 with hashing on the chip, block diagram, rig view, auto-flash, `--sim`, `--check` |
| **`host/hash_jobs.py`** | pin words for any hash job at any K (also copied to `sha3-only` `test/`) |
| **`host/test_variant.py`** | hash jobs (and the NTT check) on the FPGA, over USB or the rig |
| **`tools/tile_exp.py`**, **`tools/tile_exp_results.json`** | tile experiments: build a variant from a branch, test, harden; all results |
| **`tools/harden_times.py`** | per-stage harden times from LibreLane's `runtime.txt` |
| **`tools/rig_pincheck.py`**, **`fpga/rig_pinchk.v`** | wiring check of the rig |
| **`tools/mlkem_profile/`** | ML-KEM-512 instruction profile on a Cortex-M33 (Unicorn) |
| **`sim/route_model.py`** | ML-KEM-512 exchange time of every route, incl. the RP2350's feed, bursts and CBD |
| **`fpga/sim_variant/`** | pin-level cocotb hash test of any tile-experiment variant |
| **`fpga/70-raspberrypi-pico.rules`** | udev rule for the Pico's serial port |
| **`docs/TILE_ROUTES.md`**, **`docs/SHA3_ONLY_3X2.md`** | copies of the team docs: tile routes, 3×2 signoff |
| `fpga/` | Tang Nano rig: `Makefile` (`TARGET=pico`, `DESIGN_ROOT`, `BUILD_TAG`, `CHPARAM`), wrappers, `PROTOCOL.md` (TTE1) |
| `host/tt_emu.py` | TTE1 driver (Tang USB or Pico bridge) |
| `host/showcase.py` + `.html`, `host/test_ntt.py` | the NTT chip's demo and byte test |
| `model/`, `sim/` | FIPS 203 model, NTT chip cycle model, performance model |
| `docs/PICO_TANG_RIG.md`, `docs/FPGA_DEMO.md`, `docs/ESTIMATES.md` | rig, demo, how the estimates are built |

## 6. The rig

- **Wiring.** A Pico 2 W drives a Tang Nano 20K over 26 wires plus ground. The wires are verified. The
  FPGA runs the chip's RTL (hash chip: ring core with enable flops, `CLOCK_GATING 0`). The Pico runs the
  team firmware `tt_ntt_pico2w_tang.uf2`, whose TTE1 bridge the PC drives over `/dev/ttyACM0`.
- **Bitstreams** (in `fpga/build/`):
  - `tt_um_NTT_Core_hashonly_k8_pico` (the demo);
  - `_hashonly_k8` (Tang USB);
  - `_hashonly_k16_pico` (K = 16, built, not run);
  - `tt_um_rig_pinchk_pico` (wiring check);
  - the NTT builds.
- **Speed on the rig.** About 37 µs per chip clock over USB if every clock is sent; the demo sends only what
  changed and reads only the output clocks, so an exchange takes 0.35 s.
- **Resources** (hash chip, Pico build): 2,025 LUT4, 1,745 DFF, logic up to 144 MHz.

## 7. Key numbers

**Tile matrix** (measured, LibreLane on this machine; "relaxed" is the team's recipe: 0.14 ns hold SDC,
small cells, no `clkdlybuf`, density 75). Core area: 2×2 72.6k µm², 3×2 110.9k µm².

| Variant | Tile | Synth | Result | Harden time |
|---|---|---|---|---|
| NTT chip (`main`) | 2×2 | 31.8k | clean, 52.5 %, +1.41 ns | 5.4 min |
| SHA-only K = 2 | 2×2 | 38.3k | clean, 65.1 %, +9.93 ns | 5.8 min |
| SHA-only K = 4 | 2×2 | 41.1k | clean, 71.4 %, +7.11 ns | 84.9 min (83 of them routing) |
| SHA-only K = 8 | 2×2 | 47.0k | does not route (9,660 violations after 60 min) | stopped |
| SHA-only K = 8, TT default config | 2×2 | 57.9k | does not place (82.7 %) | 2.9 min |
| SHA-only latch core | 3×2 | – | stalls in post-CTS repair (75 min, no progress) | stopped |
| **Hash chip K = 8 + CBD** | **3×2** | **48.6k** | **clean, 55.5 %, +8.17 ns, hold +0.018 ns** | **44.8 min** |
| Hash chip K = 8 + CBD | 2×2 | 48.6k | does not route (83.6 % after CTS; 23,058 violations) | stopped |
| Hash chip K = 16 + CBD | 3×2 | 60.8k | does not route (69.2 % after CTS; 32,578 violations after 1 h 40 min) | stopped |

| Number | Value | Tag |
|---|---|---|
| ML-KEM-512 exchange, RP2350 alone | 8.08 ms | cited (pqm4) |
| + hash chip K = 8, PIO feed | **3.18 ms, 2.54×** (hashing 5.81 → 1.09 ms) | model, `sim/route_model.py` |
| + hash chip K = 8, firmware as written | 4.57 ms, 1.77× | model |
| + hash chip K = 16 (needs 4×2) | 2.87 ms, 2.82× | model |
| + NTT chip, optimized firmware | 8.88 ms, 0.91× | model |
| Keccak-f[1600] on the chip | 368 clocks = 7.4 µs at 50 MHz (K = 8) | measured RTL |
| Hash chip power | 3.75 mW | OpenROAD estimate |
| Burst + CBD helper area | 1.6k µm² | measured (48.6k vs 47.0k) |
| Harden on this laptop | 5–6 min uncongested; 45–85 min when routing is tight; at most 3 runs at once on 15 GB, `DRT_THREADS=6` | measured |

## 8. Decisions taken, and why

- **Hash-only chip on its own branch, not on `main`.** `main` stays the team's NTT chip until the team
  chooses. Viktor asked for the NTT to be cut and the hasher optimized.
- **K = 8 in 3×2.** It's the fastest core that routes. K = 16 doesn't route in 3×2, and K = 8 doesn't route
  in 2×2.
- **The CBD helper is in; the rejection sampler (SampleNTT) is not.** Its 12-bit variable-rate output
  can't be returned compacted without a handshake pin, so it would save no host work (1.7 % of the chain).
- **The pin protocol is unchanged from `sha3-4x2`** (hash words = `uio[3:0]` 0xF), so existing host code
  runs. Bursts and CBD are new commands 5 and 6.
- **The demo is one script.** It loads the FPGA itself. Its headline is the board model (RP2350 vs chip),
  and every run is checked byte for byte.

## 9. Open items, most urgent first

1. **Team decision: NTT chip (2×2) or hash chip (3×2).** The numbers are in chipathon-2026
   `docs/tile_routes.md` and `docs/sha3_only_3x2.md`.
2. **Ask Tiny Tapeout about the custom SDC** (0.14 ns hold uncertainty). Every ring-core route needs it.
3. **Before tapeout of the hash chip:**
   - the TT precheck and a gate-level test;
   - a look at the 1,739 slow-corner slew warnings;
   - a top-module name (still `tt_um_NTT_Core`).
4. **RP2350 firmware hash path, measured on the rig.** `rp2350/core/sha3_sw.c` (software SHA-3 + CBD) is
   committed on `sha3-only` but not yet called. Next:
   - a TTE1 `HASH` command: the PC sends a message, the RP2350 builds the pin words, runs them on the chip
     with PIO, also runs the hash in software, and returns both cycle counts;
   - a `SET_HZ` command to run the rig's chip clock above 13.5 MHz, with skew calibration;
   - after that, the demo can show RP2350-vs-chip **measured on the real RP2350**, not modelled.

   Flashing the Pico needs BOOTSEL: the SDK's 1200-baud reset works over `/dev/ttyACM0`.
5. **Developer page in the demo** (requested): web buttons to flash the FPGA with the hash chip K = 8 / 16,
   the pin check or the NTT chip; wiring check; self-test; clock sweep; Pico status. Planned with item 4,
   together with folding the page into the single script in the full SAF dark style (black, Archivo, red
   pill buttons).
6. **The footer says "team representing SAF Tehnika".** Confirm the wording before anyone outside the team
   sees it. No SAF logo is used; only the colours and the Archivo typeface.
7. **The presentation deck and the Q&A page** (claude.ai artifacts) predate the hash chip. Update them only
   when Viktor asks.

## 10. Gotchas

- **The Tang Nano forgets its image at power-off.** The demo reloads it. Its USB debugger (BL616) sometimes
  hangs a flash or goes silent; the demo retries, and otherwise unplug and replug the Tang.
- **One program per serial port.** Stop the demo (Ctrl+C) before other rig tools. Find servers with
  `ss -ltnp 'sport = :8080'`. **Never `pkill -f` a pattern that appears in your own command line:** it kills
  your shell.
- **`tools/tile_exp.py run NAME` deletes that experiment's folder first**, `runs/` included. Copy a GDS you
  want to keep before rerunning.
- **Memory.** The detailed router's memory grows with its threads. More than three hardens at once crashed
  this 15 GB machine.
- **The ring core needs the custom hold SDC.** With TT's default config it doesn't fit (1,590 hold buffers,
  per the team).
- **`/dev/ttyACM0` needs the udev rule** `fpga/70-raspberrypi-pico.rules` (installed).
- **Hardware results are bytes at fixed clock positions.** There is no valid flag; `0x00` elsewhere means
  nothing.
