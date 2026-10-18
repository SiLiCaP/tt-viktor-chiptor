![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# tt-viktor-chiptor: ML-KEM NTT coprocessor workbench

Viktor's exploration and verification workbench for the Chipathon 2026 team chip: an NTT coprocessor for
post-quantum ML-KEM-512 (FIPS 203) on Tiny Tapeout, 2×2 tiles. The tapeout design (`tt_um_NTT_Core`) and the
RP2350 firmware live in the team repo [chipathon-2026](https://github.com/SiLiCaP/chipathon-2026). This
repo holds what proves and demonstrates them:

- **Models:** a FIPS 203 golden model, and a cycle-exact model of the chip's pins (`model/`, `sim/`).
- **Tang Nano 20K rig** (`fpga/`): runs the team chip's **hardened sky130 gate netlist**. Full ML-KEM-512
  exchanges match the model byte for byte.
- **SHA-3 demo website** (`host/sha3_demo.py`), for the hash-only chip (chipathon-2026 branch `sha3-only`):
  ML-KEM-512 with every hash call on the chip through the Pico 2 W + Tang Nano rig, a live block diagram of
  which step runs when and where, the rig's traffic, hashing anything, and performance.
- **NTT demo website** (`host/showcase.py`), for the NTT chip on `main`: polynomial multiplication, key
  exchange, encrypted messages, attacks, performance, and the RP2350 + chip system.
- **Pico 2 W + Tang Nano rig** ([docs/PICO_TANG_RIG.md](docs/PICO_TANG_RIG.md)): the RP2350 firmware drives the
  chip's gate netlist over 26 wires and logs its own timing, which feeds the silicon estimate
  ([docs/ESTIMATES.md](docs/ESTIMATES.md)). That precise simulation needs both boards connected.
- **Performance and architecture studies:** `sim/perf_model.py`, `sim/arch_explore.py`,
  `sim/sha3_options.py`, `docs/ARCHITECTURE_OPTIONS.md`, `docs/spec-changes/`.
- **An earlier chip version** (`src/`, `tt_um_ntt_engine`), with its tests.

**Start here: [docs/HANDOFF.md](docs/HANDOFF.md)** covers what is proven, how to rerun it, the key numbers
and the open items. To run the demos: [docs/FPGA_DEMO.md](docs/FPGA_DEMO.md).

```bash
source ~/tools/oss-cad-suite/environment
make -C fpga prog                     # team chip (gate netlist) onto the Tang Nano
python3 host/test_ntt.py --seeds 3    # ML-KEM-512 on the FPGA, every byte checked
python3 host/showcase.py              # http://localhost:8080   (--sim: no board needed)
python3 host/sha3_demo.py             # the hash-only chip on the Pico rig (--sim: no board needed)
```

This repo is based on the Tiny Tapeout Verilog template. See https://tinytapeout.com for the TT docs.
