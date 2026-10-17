# Running the chip on the Tang Nano 20K, and the presentation demo

This runs the chip's real Verilog (`src/`) on the FPGA. The PC plays the RP2350. It streams
coefficients into the chip's pins and reads the result bytes back, clock for clock.

## One-time setup (already done on Viktor's machine)

1. OSS CAD Suite in `~/tools/oss-cad-suite`, plus Python packages. See `fpga/README.md`.
2. The USB permission rule `fpga/70-tangnano20k.rules`, installed in `/etc/udev/rules.d/`.

## Every time

Plug in the board, then in a terminal:

```bash
cd ~/Documents/Projects/Chipathon2026/tt-viktor-chiptor
source ~/tools/oss-cad-suite/environment
make -C fpga prog                 # build and load the chip into the FPGA (~20 s)
python3 host/tt_emu.py --ping     # should print: /dev/ttyUSB1: magic TTE1 OK
python3 host/demo.py              # the demo (~15 s), figures go to reports/demo/
```

`make -C fpga prog` loads into SRAM, which is lost when the board loses power. Run it again after
every replug. `make -C fpga flash` makes it permanent, but it replaces the factory LiteX demo.

## What the demo shows

1. **Polynomial multiply (team Spec 1 demo).** Two random polynomials go through forward NTT,
   forward NTT, basemul, inverse NTT and scale, all on the chip. The CPU checks the answer with a
   schoolbook multiply: 256/256 coefficients must match.
2. **ML-KEM-768 key exchange.** Alice generates keys, Bob encapsulates, Alice decapsulates.
   Every NTT, basemul and scale runs on the chip; hashing and encoding stay on the PC. The two
   shared keys must be equal and identical to a pure-software FIPS 203 run.

It's the real coprocessor loop, not a replay: the PC sends one NTT layer, reads the chip's results,
and builds the next layer from them.

## Files for the slides (`reports/demo/`)

| File | Use it for |
|---|---|
| `01_pin_timing.png` | How the chip talks: valid/sof, coefficients in, result bytes out after the fixed delay D |
| `02_polymul.png` | Proof it computes correctly: chip result on top of the CPU reference |
| `03_clocks_per_call.png` | Speed per operation (clocks, and µs at 50 MHz) |
| `04_mlkem768_chip_work.png` | What the chip does inside one ML-KEM-768 key exchange |
| `pins_forward_ntt.vcd` | Live waveform: `surfer reports/demo/pins_forward_ntt.vcd` (or `gtkwave …`) |

Rehearse without the board: `python3 host/demo.py --sim`. It uses the Python model, and the
pin figure's title then says "simulated".

## Live interactive demo (for presenting)

```bash
python3 host/live_demo.py          # chip on the Tang Nano (or --sim without the board)
# then open http://localhost:8080 in the browser
```

| Button | What happens |
|---|---|
| **1 · Exchange keys** | Alice runs keygen and Bob encapsulates, both with every NTT/basemul on the chip; then Alice decapsulates. The chip-call counters run live, and the keys match |
| **2 · Send encrypted packet** | Bob encrypts your message with the shared key; Alice authenticates and decrypts it |
| **Eve: tamper ciphertext** | One bit flipped in Bob's ML-KEM ciphertext: Alice's key silently becomes unrelated (implicit rejection) |
| **Eve: tamper packet** | One bit flipped in the packet: the MAC rejects it |
| **Eve: eavesdrop** | Eve has everything on the wire, but no key that opens the packet |
| **Eve: timing attack** | 3 key generations with different secrets: chip clocks are identical (constant time) |
| **host-side masking** toggle | Shows the chip-specific risk and its fix. Without masking, Eve probing Alice's chip pins during keygen recovers **256/256** secret coefficients, because layer 1 of the NTT carries them in the clear. With masking she sees uniform noise (0/256), at the cost of 2× chip calls |

The performance panel shows, per operation: the measured run (host + chip), pure Python, the
coefficients, and the predicted RP2350 and RP2350 + chip times. An exchange takes about 11 s on the board
(22 s masked), almost all of it USB; on silicon the chip part takes about 1 ms.

## Performance log and the coefficients

```bash
python3 tools/perf.py bench        # Python-only vs chip on FPGA, + predictions; appends to perf/perf_log.jsonl
python3 tools/perf.py plot         # reports/perf/01_journey.png, 02_measured_vs_predicted.png
python3 tools/perf.py show         # the whole log as a table
```

Every run of `demo.py`, `live_demo.py` and `perf.py bench` is appended to `perf/perf_log.jsonl`,
which is committed, so the speed history is kept. The first entries are the numbers measured
earlier on Oct 17: RTL simulation, the 115.2 kbaud FPGA replay, gate-level simulation, and the 1 Mbaud replay.

The coefficients (`sim/perf_model.py`; every input is in `sim/config.py`, marked cited, measured or ASSUMPTION):

- **K_py** = RP2350 software time / Python-only time. RP2350 time = pqm4 m4fspeed cycles / 150 MHz.
- **K_host** = RP2350 host-side time / Python host-side time, for the work the chip never touches:
  pqm4 cycles minus the cited software cost of the offloaded calls (ePrint 2022/112).
- **K_chip** = chip time on silicon / chip time on the FPGA. Silicon chip time = exact protocol clocks
  per call / f_chip, plus RP2350 bookkeeping. f_chip is the lowest of: the 50 MHz timing target, the measured
  STA (87 MHz typical, 44.8 MHz slow corner), the 50 MHz I/O assumption and the PIO limit.

Predicted RP2350 alone = Python-only × K_py. Predicted RP2350 + chip = host part × K_host + chip part × K_chip.

### Getting data to the chip: PIO + DMA

The pins move one word per chip clock in every scenario (PIO lockstep). What changes is the RP2350's
own work per butterfly: building the input words, unpacking the 3 result bytes, and the index math.

| Scenario | Model | Per NTT (50 MHz) |
|---|---|---|
| CPU-serial | CPU packs, then waits for each transfer | 175 µs |
| **PIO + DMA** (default) | double-buffered: CPU work overlaps the stream | 75 µs (CPU-bound) |
| PIO + DMA, 2 cores | packing and unpacking split over both M33 cores | 56.5 µs (pin-bound) |
| pins only | the protocol stream alone, the floor for any host | 53.9 µs |
| RP2350 software (cited) | Cortex-M4 NTT, 5,992 cycles at 150 MHz | 39.9 µs |

The output pins carry 3 bytes per butterfly, so at 50 MHz a single NTT can't go below 54 µs.
DMA removes the host overhead but not that floor.

### Only the chip's part

```bash
python3 tools/perf.py chippart     # Python vs FPGA vs RP2350 software vs silicon, NTT/INTT/basemul/scale only
```

For one ML-KEM-768 key exchange (measured Oct 17), see `reports/perf/03_chip_part_only.png`:

| | time |
|---|---|
| pure Python on the PC (measured) | 3.7 ms |
| chip on the FPGA over USB (measured) | 11.2 s |
| RP2350 software (cited cycles) | 1.32 ms |
| silicon, pins only | 2.82 ms |
| RP2350 + chip, CPU-serial / PIO+DMA / 2 cores | 6.59 / 3.48 / 3.00 ms |

**Current result:** with PIO+DMA the whole operation comes out 0.83–0.90× the speed of the RP2350
alone. Two things hold it back:
1. The chip's part is pin-bound at 3 clocks per butterfly, and the M33's software NTT is faster than that.
2. Most of ML-KEM is hashing (67–75%), which this chip doesn't do.

Ways forward: more work per transferred word (on-chip storage, like the handoff's design B3), and
SHA-3 on chip (option b).

## More checks

```bash
python3 host/test_ntt.py                      # replay the test stimulus, every byte compared
python3 host/test_ntt.py --mlkem ML-KEM-768   # replay a full key exchange (141k clocks, ~8 s)
```

## LEDs

- **LED0** blinks: the FPGA is configured.
- **LED1:** a command is running. It looks dim during tests because it flickers.
- **LED2:** UART bytes are arriving.

## If something's wrong

- **`--ping` gets no answer:** unplug the board, plug it back in, and run `make -C fpga prog` again.
  The USB bridge can get stuck. See `fpga/README.md`.
- **"Permission denied" on `/dev/ttyUSB1`:** the udev rule is missing. See `fpga/README.md`.
