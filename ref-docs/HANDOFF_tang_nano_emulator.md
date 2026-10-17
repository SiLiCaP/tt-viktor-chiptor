# Handoff: PC-driven Tang Nano 20K emulator for our Tiny Tapeout design

You are working inside our Tiny Tapeout Verilog template repo (`src/`, `test/`, `info.yaml`, cocotb setup already present). Your task is to build a **test harness that runs our `tt_um_*` module on a Sipeed Tang Nano 20K FPGA and drives it from a PC over USB-UART**, so the PC plays the role of the RP2350 on the TT demo board. We don't have the RP2350 board yet.

Read the whole file before starting. Ask me before changing anything under `src/` or `info.yaml`.

---

## 1. Project context (short)

- **Event:** Tiny Tapeout hackathon, 5-person team. Budget is 4–6 tiles, digital only, no analog pins.
- **Project:** an **ML-KEM (FIPS 203) NTT coprocessor**. The chip does only the polynomial arithmetic: forward NTT, inverse NTT, basemul (pointwise multiplication in the NTT domain) and scale by 128⁻¹. The host does everything else: SHAKE/SHA-3, sampling, compression, encoding, the re-encrypt-and-compare check, and storing all polynomials.
- **Host on the real board:** the **RP2350**, not the RP2040. On the FPGA rig, the **PC** is the host.
- **Math constants:**
  - q = 3329, ζ = 17, n = 256.
  - 7 NTT layers × 128 butterflies = 896 butterflies per NTT.
  - Twiddle ROM: 128 × 12 bit, `ZETAS[i] = 17^bitrev7(i) mod q`.
  - 128⁻¹ mod q = 3303.
- **Golden model:** `mlkem_ntt_model.py` (I'll give you this file). Put it at `model/mlkem_ntt_model.py`. It contains:
  - FIPS 203 `ntt_ref`, `intt_ref`, `basemul_ref`.
  - `ct_butterfly` / `gs_butterfly`.
  - `barrett()`: m = 5039, shift 24, at most 2 conditional subtracts, exact for all x < q².
  - `ntt_blocked()`: the 2-pass, 16-coefficient schedule, see §2.

  Running `python3 model/mlkem_ntt_model.py` self-checks everything.

## 2. Chip interface (agreed pin map)

All 24 pins carry data or control. `clk`, `rst_n` and `ena` are separate pins.

| Pins | Dir | Meaning |
|---|---|---|
| `ui_in[7:0]` + `uio_in[3:0]` | in | one 12-bit coefficient per clock: `{uio_in[3:0], ui_in[7:0]}` |
| `uio_in[4]` | in | `valid`: this clock carries real data |
| `uio_in[5]` | in | `sof`: start of frame, resets the chip's counters |
| `uio_in[7:6]` | in | `op[1:0]`: 00 = forward NTT (CT), 01 = inverse NTT (GS), 10 = basemul, 11 = scale |
| `uo_out[7:0]` | out | result bytes. Two 12-bit coefficients are packed into 3 bytes, using ML-KEM ByteEncode12 order (little-endian bit packing) |
| `uio_oe` | | `8'h00`: all bidirectional pins are inputs |

There is **no handshake or back-pressure**. The chip has a **fixed, data-independent latency**, which is also a security requirement (constant time). The host drives inputs and samples outputs in lockstep. The emulator must therefore support **cycle-exact streaming**, not just register-poke debugging.

There are two chip architectures and the decision is still open. The emulator must support both, because both are fixed-latency lockstep streams.
- **A. Butterfly streaming:** the host sends (a, b) per butterfly in canonical order, the chip looks up ζ from its ROM via an internal counter, and returns 3 bytes. That's ~3 clocks per butterfly and ~2,700 clocks per NTT.
- **B. 16-coefficient block:** the host streams 16 coefficients and the chip runs several layers locally, then streams 24 bytes back.
  - Pass 1 takes groups `{r, r+16, …, r+240}` and runs layers len = 128, 64, 32, 16.
  - Pass 2 takes contiguous blocks of 16 and runs layers len = 8, 4, 2.
  - That's ~768 I/O clocks per NTT. The on-chip buffer also enables shuffled butterfly order as a side-channel countermeasure.

## 3. What to build

### 3.1 FPGA side: `fpga/` (new directory, never listed in `info.yaml`)

- `fpga/tangnano20k_top.v`: wrapper that instantiates the **unmodified** `tt_um_*` module from `src/`.
- **UART engine:** RX/TX, 8N1. Start at 115200 baud and make the rate a parameter so we can try 1–3 Mbaud later.
- **Command processor** using the protocol in §3.2.
- **Stimulus RAM:** ≥ 8192 × 16 bit, one `{uio_in, ui_in}` word per DUT clock.
- **Capture RAM:** ≥ 8192 × 24 bit, `{uio_oe, uio_out, uo_out}` per DUT clock.
- Infer both RAMs with plain Verilog arrays so Yosys maps them to BSRAM. The GW2AR-18 has plenty.
- **DUT clock:** for v1, a fabric-generated clock toggled by the wrapper.
  - *Step mode:* one pulse per command.
  - *Run mode:* free-running at `sysclk/2` or slower, with a selectable divider.
  - Route it through a global clock buffer if the toolchain needs one.
  - Drive DUT inputs on the **falling** edge of the DUT clock and sample outputs just before the **rising** edge. This matches how a PIO host will drive the real chip.
- **Reset:** the wrapper controls `rst_n` and holds it low for N DUT clocks on command. `ena = 1` always.
- **LEDs:** a heartbeat plus "run in progress". The LEDs are active-low on this board, I believe; verify.
- `fpga/tangnano20k.cst`: pin constraints.
  - The 27 MHz crystal input, and the UART TX/RX that go to the onboard BL616 USB bridge.
  - I believe the UART is around pins 69/70 and the clock is pin 4, but **verify every pin against Sipeed's official Tang Nano 20K schematic/examples**. Don't guess.
- `fpga/Makefile` using the open-source flow (OSS CAD Suite):
  - `yosys -p "synth_gowin -top tangnano20k_top -json build/top.json"` with `src/*.v` and `fpga/*.v`.
  - `nextpnr-himbaechel --json … --write … --device GW2AR-LV18QN88C8/I7 --vopt family=GW2A-18C --vopt cst=fpga/tangnano20k.cst`.
  - `gowin_pack -d GW2A-18C -o build/top.fs …`.
  - `openFPGALoader -b tangnano20k build/top.fs`. Add a separate `flash` target with `-f`.

  Check the exact flags against the installed tool versions. Gowin EDA is an acceptable fallback if the open flow fails, but keep the open flow as the default.
- Must work on **Linux and Windows**. On Windows, document any USB driver step that openFPGALoader needs.

### 3.2 Host protocol (binary, little-endian)

Every command starts with a 1-byte opcode. Every response starts with `0xA5` followed by a status byte (0 = OK).

| Op | Name | Payload | Response |
|---|---|---|---|
| `0x00` | PING | none | `0xA5 00` + 4-byte version/magic |
| `0x01` | RESET | u16 cycles | ok |
| `0x02` | SET_IN | u8 ui_in, u8 uio_in | ok |
| `0x03` | STEP | u16 n | ok + u8 uo_out, u8 uio_out, u8 uio_oe (after the last step) |
| `0x04` | SET_DIV | u8 run-mode clock divider | ok |
| `0x10` | LOAD | u16 addr, u16 len, len × u16 words | ok |
| `0x11` | RUN | u16 len | ok, after playing `len` stimulus words at full DUT speed and capturing `len` outputs |
| `0x12` | READ_CAP | u16 addr, u16 len | ok + len × 3 bytes |

Keep it simple and extensible. If you find a cleaner design, propose it to me first, then document it in `fpga/PROTOCOL.md`.

### 3.3 PC side: `host/` (Python 3, `pyserial`)

- `host/tt_emu.py` defines a `TTEmu(port, baud)` class:
  - `ping()`, `reset(n)`, `set_inputs(ui, uio)`, `step(n) -> (uo, uio_out, uio_oe)`.
  - `run_stream(words) -> captured` handles LOAD + RUN + READ_CAP, chunking past RAM size.
  - Port auto-detect with a `--port` override. The board shows up as two USB interfaces and the UART is one of them.
- `host/mlkem_link.py`: helpers that turn polynomials into stimulus words using the §2 pin map, and turn captured bytes back into coefficients, including ByteDecode12 and finding the fixed latency offset.
- `host/test_example.py`: bring-up test against the **template's existing example design**. Run thousands of random `ui_in`/`uio_in` vectors in both step and run mode and compare with the expected result, e.g. `uo_out = ui_in + uio_in` if that's what the template does; read `src/project.v` to check.
- `host/test_ntt.py`: placeholder for when the NTT RTL exists. Generate random polynomials, stream them, compare with `model/mlkem_ntt_model.py`, and report the first mismatching coefficient and its cycle.
- **Design rule:** the stimulus/expected-result generators live in `model/` or `host/` and must be importable by **both** this script and the cocotb tests in `test/`. That way one golden model checks simulation and FPGA.

## 4. Rules (do not break)

1. `src/` must stay pure, portable Verilog. No vendor primitives, no `initial` blocks, every register reset. The FPGA build uses the **same** `src/` files as the ASIC flow.
2. Wrapper, constraints, Makefile and PLL/clock code live only in `fpga/`. `info.yaml` `source_files` must not reference `fpga/`.
3. The template's GitHub Actions (docs, test, GDS) must stay green. Run the existing cocotb test before and after your changes.
4. Order of trust: cocotb simulation, then the Tang Nano, then real silicon. If the FPGA and the simulation disagree, assume the wrapper or timing is wrong first.

## 5. Acceptance criteria (v1 done when)

- [ ] `make -C fpga` builds a bitstream from a clean checkout. `make -C fpga prog` loads it.
- [ ] `python host/tt_emu.py --ping` gets the magic back, on Linux; Windows is documented if untested.
- [ ] `host/test_example.py` passes ≥ 10,000 random vectors in step mode and in run mode at the highest stable divider.
- [ ] A run of 8192 stimulus words completes, and the capture matches a cycle-accurate Python expectation including pipeline offset.
- [ ] `fpga/README.md` covers toolchain install (Linux + Windows), build, flash, pinout used, protocol summary, and how to point it at a new `tt_um` top.

## 6. Later, not now

- Swap in the NTT RTL once it exists and run `host/test_ntt.py`.
- Raise the baud rate and DUT clock, and report the achieved speed.
- A Raspberry Pi Pico 2 (RP2350) wired to the Tang Nano as the host, with a PIO lockstep driver. That's the real-board path before silicon arrives.

When you finish each acceptance item, tell me what you verified and how. If a pin, flag or tool behavior is uncertain, say so instead of guessing.
