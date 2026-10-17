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
