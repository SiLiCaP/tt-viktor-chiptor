# The FPGA demo: ML-KEM-512 with SHA-3 on our chip

One script runs the whole demo: `host/sha3_demo.py`. It drives the hash-only chip (chipathon-2026 branch
`sha3-only`, the 3×2 tapeout candidate) on the Pico 2 W + Tang Nano 20K rig and serves the demo page.

```bash
python3 ~/Documents/Projects/Chipathon2026/tt-viktor-chiptor/host/sha3_demo.py
```

Open http://localhost:8080 and click **▶ Run a key exchange on the chip**. Stop it with Ctrl+C.

## What the script does on start

1. **Python.** It finds the Python with pyserial: from a plain shell it restarts itself under the OSS CAD
   Suite's Python, so nothing needs sourcing first.
2. **Board.** It opens the Pico 2 W on `/dev/ttyACM0`, or the port given with `--port`, and sets the rig's
   chip clock to 13.5 MHz.
3. **Chip.** It checks that the FPGA answers like the hash chip, with one SHA3-256 against hashlib. If not
   (the Tang Nano forgets its image when power-cycled), it loads the chip with openFPGALoader:
   - it retries if the Tang's USB debugger stalls;
   - if the bitstream has never been built, it builds it first from the `sha3-only` worktree (about 2
     minutes).
4. **Page.** It serves the page.

| Option | Effect |
|---|---|
| `--flash` | always reload the chip into the FPGA first |
| `--no-flash` | never touch the FPGA |
| `--port /dev/ttyUSB1` | the Tang Nano alone over its own USB UART, no Pico |
| `--sim` | no boards: a pin-level Python model of the chip (it passes the same 42 jobs as the FPGA) |
| `--check` | 42-job self-test plus one key exchange, printed, then exit |
| `--http 8090` | another port |

## What the page shows

- **Headline: one ML-KEM-512 exchange on the Tiny Tapeout board.**
  - The RP2350 alone takes 8.08 ms; with our SHA-3 chip it takes 3.18 ms, **2.54× faster**.
  - The hashing itself drops from 5.81 ms to 1.09 ms.
  - This is a model: cited pqm4 cycle counts for the RP2350, and the chip's exact clock counts from the
    run you just did at 50 MHz, including the RP2350's feed.
- **ML-KEM-512 map.** The block diagram of KeyGen, Encaps and Decaps:
  - chip blocks (red) are the SHA-3 / SHAKE calls, which run on the chip through the real pins;
  - RP2350 blocks are the NTT, matrix, rejection sampling and encoding, done by the PC in its place;
  - the running block lights up, and "Where it runs now" shows which side works;
  - clicking a block lists its hash calls, each checked against hashlib;
  - a timeline shows the exchange on the TT board (model) or as measured on the rig, with a replay;
  - a pace selector slows the run down to follow it.
- **The rig.** Every hash call's USB traffic and time, animated.
- **The chip.** Pinout, commands, signoff facts, and a 42-job self-test button.
- **Hash on the chip.** Any text through SHA3-256 / SHA3-512 / SHAKE128 / SHAKE256, checked against hashlib,
  with where the clocks go.
- **Performance.** The route model's exchange times and the last run per operation.

Every run checks itself: all 32 hash calls of an exchange must equal hashlib, and the keys must equal
pure-software FIPS 203. Measured on the rig: about 0.35 s per exchange, 42,900 chip clocks.

## How it moves data

The PC plays the RP2350 and turns each hash call into pin words. Each call goes to the Pico's TTE1 bridge
as LOAD / RUN / READ_CAP:
- **LOAD:** only the words that differ from the bridge's RAM are sent. The permutations' idle clocks are
  zeros and mostly stay in place.
- **READ_CAP:** only the clocks that carry output are read back.

This took an exchange from 1.6 s to 0.35 s. On the Tiny Tapeout board, the RP2350 drives the pins itself
with PIO at the chip's clock, so USB disappears.

## If something's wrong

- **"could not load the FPGA":** unplug and replug the Tang Nano's USB cable, then run the script again.
- **"does not answer like the hash chip" after loading:** check the wiring with
  `python3 tools/rig_pincheck.py` (needs the pin-check bitstream, see [PICO_TANG_RIG.md](PICO_TANG_RIG.md)).
- **"Address already in use":** another demo is still running. Find it with `ss -ltnp 'sport = :8080'`.
- **Permission denied on `/dev/ttyACM0`:** install the udev rule once:
  `sudo cp fpga/70-raspberrypi-pico.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger`.

Wiring, safety and bring-up of the rig: [PICO_TANG_RIG.md](PICO_TANG_RIG.md). The NTT chip on `main` has its
own tools (`host/showcase.py`, `host/test_ntt.py`), described in [HANDOFF.md](HANDOFF.md).
