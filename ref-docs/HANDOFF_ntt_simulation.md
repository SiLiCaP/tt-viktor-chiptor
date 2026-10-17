# Handoff: ML-KEM NTT coprocessor, from Python simulation to logic blocks

You are working in our Tiny Tapeout Verilog template repo (`src/`, `test/`, `info.yaml`, cocotb already set up).

**The job:** build a simulation of our ML-KEM NTT coprocessor **at pin level**, including the 24 I/O pins and the RP2350 host traffic, because the pins are the bottleneck.

- **Start in pure Python.** Then replace the Python model block by block with Verilog, checked against the Python at every step.
- **Later stage:** a Tang Nano 20K FPGA rig, specified in a separate handoff, `HANDOFF_tang_nano_emulator.md`.

Read this whole file first. Work stage by stage (section 7). Don't start a stage before the previous one's acceptance checks pass. Ask me before touching `src/` or `info.yaml`, and before choosing the `tt_um_*` module name.

Files that come with this handoff (put them where noted):

| File | Put at | Trust level |
|---|---|---|
| `mlkem_ntt_model.py` | `model/mlkem_ntt_model.py` | **Verified golden model.** Run it: every check prints OK. It is the spec for all arithmetic, twiddle indexes and schedules. |
| `reference/area_model/*.v`, `zeta_rom.vh` | `reference/area_model/` (not `src/`) | **Unverified sketch**, written only to measure area. It was never simulated. Use it for structure ideas only; never copy it into `src/` without tests. |

---

## 1. Project context

- **Team and event:** 5-person team at a Tiny Tapeout hackathon. After day 1, about 2 people × a few hours/day for a month.
- **Process and size:** sky130, digital only. **4 tiles (2×2) guaranteed**, 6 if critically needed.
- **Host:** the TT demo board's **RP2350**, which drives all project pins and the clock. We have a Tang Nano 20K now and the RP2350 later.
- **What we build:** a **coprocessor for ML-KEM (FIPS 203) polynomial arithmetic**. It is *not* a full ML-KEM chip. The RP2350 runs ML-KEM and offloads the NTT, inverse NTT (INTT), basemul and scale.
- **Prior art:** existing Tiny Tapeout designs include two single NTT butterflies (host supplies the twiddle) and one ML-KEM ciphertext-compare backend. Nobody has done a full NTT engine.

## 2. ML-KEM in one page, and where the chip sits

ML-KEM has three operations. Every polynomial has 256 coefficients mod q = 3329 (12 bits each). k = 2 for ML-KEM-512, k = 3 for ML-KEM-768.

| Operation | Steps (RP2350 unless marked **CHIP**) |
|---|---|
| KeyGen | 1. random seeds d, z<br>2. SHA3-512(d) → ρ, σ<br>3. sample matrix Â from SHAKE128(ρ), already in NTT form<br>4. sample s, e from SHAKE256(σ), centered binomial with small values<br>5. **CHIP: NTT(s), NTT(e)**<br>6. **CHIP: basemul Â∘ŝ**; the RP adds ê → t̂<br>7. encode ek = (t̂, ρ) and dk |
| Encaps | 1. random m<br>2. SHA3-512(m, H(ek)) → K, r<br>3. decode t̂, re-sample Â from ρ<br>4. sample r, e1, e2 (CBD)<br>5. **CHIP: NTT(r)**<br>6. **CHIP: basemul Âᵀ∘r̂ and t̂ᵀ∘r̂, then INTT** → u, v; the RP adds noise and m<br>7. compress/encode → ciphertext c; shared key K |
| Decaps | 1. decode + decompress c → u, v<br>2. **CHIP: NTT(u)**<br>3. **CHIP: basemul ŝᵀ∘û, INTT**; the RP forms w = v − result<br>4. recover m′<br>5. SHA3-512(m′, H(ek)) → K′, r′<br>6. **re-encrypt m′**: Encaps steps 3–7 with **CHIP** steps<br>7. compare c′ = c → K′ or fallback key |

Chip calls per operation (each call = one full polynomial):

| | NTT | basemul | INTT (+scale) |
|---|---|---|---|
| KeyGen, k=2 / k=3 | 4 / 6 | 4 / 9 | 0 / 0 |
| Encaps, k=2 / k=3 | 2 / 3 | 6 / 12 | 3 / 4 |
| Decaps, k=2 / k=3 | 4 / 6 | 8 / 15 | 4 / 5 |

**Where the coefficients come from:** the chip never creates coefficients.

- Â, s, e, r, e1, e2 are produced by the RP from seeds via SHA3/SHAKE.
- t̂, ŝ, u, v are unpacked from key or ciphertext bytes, or come back from earlier chip calls.

Only NTT, INTT, basemul and scale run on the chip. Hashing, sampling, encode/decode, compress and compare never reach it. Secret material that *does* pass through the chip:

- s, during KeyGen NTT.
- ŝ, during Decaps basemul.
- r, during Encaps NTT.

**Twiddle factors are not coefficients.** They are 128 constants hard-wired in the chip's twiddle ROM:

- `ZETAS[i] = 17^bitrev7(i) mod 3329`.
- They are the same for every key and every level.

## 3. The arithmetic (all verified in `mlkem_ntt_model.py`)

- **Constants:** q = 3329, ζ = 17, n = 256, 128⁻¹ mod q = 3303.
- **NTT structure:** 7 layers × 128 butterflies = 896 butterflies per NTT. ML-KEM's NTT is "incomplete": it ends in 128 degree-1 pairs.
- **CT butterfly (forward):** `t = ζ·b mod q; a' = a + t; b' = a − t` (mod q).
- **GS butterfly (inverse):** `a' = a + b; b' = ζ·(b − a)` (mod q). After all 7 inverse layers, **scale** every coefficient ×3303.
- **Barrett reduction**, exact for every x < q² (checked exhaustively): `t = (x·5039) >> 24; r = x − t·q;` then at most 2 conditional subtracts. They must be implemented as **muxes, never as variable-time branches**.
- **Basemul** for pair i (0..127): `c0 = a0·b0 + (a1·b1 mod q)·γ_i; c1 = a0·b1 + a1·b0`.
    - γ comes from the same ROM: `γ_i = (−1)^(i&1) · ZETAS[64 + i/2]` (`basemul_gamma`).
    - That is 5 modular products per pair.
- **Design A twiddle counters** (`a_zidx_fwd`, `a_zidx_inv`): with layer 0..6 and butterfly n 0..127 within the layer, in canonical FIPS order:
    - forward `(1<<layer) + (n >> (7−layer))`
    - inverse `(127>>layer) − (n >> (layer+1))`
- **Design B 2-pass schedule** (`ntt_chip_b`, `intt_chip_b`, `b_pair`, `b_zidx`), verified including random shuffled order:
    - **Forward pass 0:** strided groups `{r, r+16, …, r+240}` (r = 0..15), layers L = 128, 64, 32, 16. Local strides are 8, 4, 2, 1. The twiddles don't depend on r.
    - **Forward pass 1:** contiguous blocks `16b … 16b+15`, layers L = 8, 4, 2.
    - **Inverse pass 2:** contiguous, L = 2, 4, 8. **Inverse pass 3:** strided, L = 16, 32, 64, 128, then scale.
    - Pair and twiddle closed forms are in `b_pair` / `b_zidx`; the RTL must match them.
- **Fact for later:** the NTT is two independent 128-point NTTs on even and odd indexes (`ntt_even_odd`). A 128 × 12 on-chip matrix could do all 7 layers in one visit, but its storage alone synthesizes to ~89,700 µm² (~5 tiles of cells), so it's out of scope.

## 4. The two chip designs

Both designs use the same pins and the same core blocks: twiddle ROM, modular multiplier + Barrett, add/sub, and the ByteEncode12 packer. A is the friend's design; B is A plus a 16-coefficient block engine.

### Pins (both)

| Pins | Dir | Meaning |
|---|---|---|
| `ui_in[7:0]` + `uio_in[3:0]` | in | 12-bit data word `din = {uio_in[3:0], ui_in}` |
| `uio_in[4]` | in | `valid`: this clock carries a word |
| `uio_in[5]` | in | `sof`: start of frame |
| `uio_in[7:6]` | in | `op`: 00 CT/NTT, 01 GS/INTT, 10 basemul, 11 scale |
| `uo_out[7:0]` | out | result bytes. Two 12-bit values → 3 bytes, ByteEncode12 order: `b0 = v0[7:0]`, `b1 = {v1[3:0], v0[11:8]}`, `b2 = v1[11:4]` |
| `uio_oe` | | `0x00`: all bidirectional pins are inputs |

There is **no output-valid and no back-pressure**. Every result appears at a **fixed, data-independent clock offset**, and the host samples in lockstep. Fixed latency is also our constant-time security requirement.

### Design A: butterfly stream

- **Hardware:**
    - Sequencer: counters for layer, butterfly and basemul pair; computes the twiddle index.
    - Input registers.
    - Twiddle ROM (one shared instance).
    - Modular multiplier: 4-bit digit-serial, 3 clocks per product.
    - Add/sub mod q, and the packer.
- **Protocol:** the host sends butterflies in canonical FIPS order.
    - **CT/GS transaction:** 2 words (a, then b) in → 3 bytes (a′, b′) out. `sof` on the first word of a polynomial resets the counters. `op` is held for the whole frame.
    - **Basemul transaction:** 4 words (a0, a1, b0, b1) → 3 bytes (c0, c1).
    - **Scale transaction:** 2 words → 3 bytes.
- **Throughput:**
    - Target 1 butterfly per 3 clocks (output-pin-bound), so the PE must be pipelined: 896 × 3 = **2,688 clocks per NTT**.
    - The host makes **7 round trips** per NTT (one per layer).

### Design B: 16-coefficient block engine

- **Hardware:** everything in A, plus:
    - 16 × 12-bit buffer with 2 read and 2 write ports.
    - Address generator (`b_pair`/`b_zidx`).
    - Shuffle LFSR, permuting the 8 butterflies of each layer.
    - Block FSM.
- **Header word:** every frame starts with one (`valid=1, sof=1`):
    - `din[2]` block mode
    - `din[1:0]` pass (0 fwd strided, 1 fwd contiguous, 2 inv contiguous, 3 inv strided)
    - `din[6:3]` block index (r or b)
    - `din[7]` shuffle enable
    - `din[11:8]` = 0
- **Stream mode** (`din[2]=0`): A's protocol exactly (ops from the op pins). Note that in B the `sof` word is a header, not data.
- **Block mode** (`din[2]=1`):
    1. 16 data words in, local index 0..15 in the host's gather order.
    2. The chip computes for a fixed number of clocks, the same with or without shuffle.
    3. 24 bytes out, back to back.
- **Clocks per NTT** (16 blocks per pass, 2 passes; each block is 16 in, then the compute, then 24 out):
    - **B1 (serial multiplier): 3,968.**
    - **B2 (parallel 12×12 multiplier, 1 butterfly/clock): 2,176.**
    - **B3 (2–3 buffers, I/O overlapped with compute): ~900–1,000**, not built yet.
- **Round trips:** 2 per NTT.
- **Basemul and scale:** stream exactly as in A. A full-polynomial basemul takes ~1,920 clocks with the serial multiplier and ~640 with the parallel one.

### Synthesized area (Yosys + ABC, sky130_fd_sc_hd typical corner, from the reference area model)

| | Cell area | % of one tile (≈17,955 µm²) | Fits |
|---|---|---|---|
| A (serial multiplier) | 24,617 µm² | 137% | 1×2 at 68% (tight) · 2×2 at 33% |
| A (parallel) | 26,719 µm² | 149% | 2×2 at 36% |
| B1 (serial) | 40,988 µm² | 228% | 2×2 at 55% |
| B2 (parallel) | 42,680 µm² | 238% | 2×2 at 57% |

**Per block** (hierarchical run):

| Block | Cell area | % of one tile |
|---|---|---|
| Sequencer + input regs | 4,840 µm² | 27% |
| Twiddle ROM | 1,600 µm² | 9% |
| Mult + Barrett, serial | 10,000 µm² | 56% |
| Mult + Barrett, parallel | 11,800 µm² | 66% |
| Add/sub + operand regs + basemul control | 7,800 µm² | 43% |
| Packer | 970 µm² | 5% |
| B: buffer | 5,770 µm² | 32% |
| B: ports + address gen + LFSR + block FSM | 10,550 µm² | 59% |

**Slot sizes:** 1×2 = 160 × 225 µm, 2×2 = 334 × 225 µm. A real Tiny Tapeout run adds roughly 10–20% (clock tree, buffers). Treat these numbers as ±10%.

**Synthesis recipe** to track area as you build:

```
pip install yowasp-yosys
curl -O https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
yowasp-yosys -p "read_verilog -sv <files>; synth -flatten -top <top>; dfflibmap -liberty <lib>; abc -liberty <lib>; opt_clean -purge; stat -liberty <lib>"
```

## 5. Security features (model them in Python from stage 1)

1. **Constant time:** cycle counts and output offsets must be identical for every input, and in B with shuffle on or off. Add a test.
2. **Masking:** host-side only, no chip change. Split a secret polynomial s into s₁ (random) and s₂ = s − s₁ mod q, transform each, and add the results (the NTT is linear). Show that bus traffic for one share looks uniformly random, e.g. a histogram or χ² test.
3. **Shuffling:**
    - In B, the chip's LFSR permutes the butterfly order inside each layer.
    - In A, the host can reorder only butterflies that share a twiddle: 128 per group in layer 1, down to 2 in layer 7. The counters only count, so this works.
    - Outputs must not change.
4. **Fault check (optional):** run twice and compare.

## 6. What "the I/O bottleneck simulation" must answer

For each design (A, B1, B2, B3) and for KeyGen/Encaps/Decaps at k = 2 and 3, report:

- Total time.
- Pin-transfer time.
- Chip-compute time.
- Host overhead.
- Which one is the bottleneck.

Make every host assumption a named parameter in one config file, labelled as an assumption until measured:

- `f_chip`: sweep 10 / 25 / 50 MHz. Check the TT docs for the real maximum.
- `f_rp`: 150 MHz.
- **Transfer mode:**
    - ideal PIO lockstep: one word or byte per chip clock
    - PIO with FIFO + CPU refill: per-word CPU cost in RP cycles, FIFO depth
    - bit-banged GPIO: RP cycles per pin update
- **Host bookkeeping:**
    - per A butterfly: index math, unpack, write-back
    - per B block: gather/scatter
- **Software baseline:** the RP2350 doing the NTT itself. Look up published Cortex-M33/M4 numbers (e.g. pqm4 benchmarks), cite them, and later replace them with a measurement on a Pico 2.

## 7. Stages and acceptance criteria

### Stage 1: pure Python

1. **`model/mlkem.py`:** full FIPS 203 ML-KEM in plain arithmetic, with no Montgomery form. Use `hashlib` (sha3_256/512, shake_128/256).
    - Make NTT, INTT, basemul and scale **pluggable through a backend object**.
    - ✅ Matches an independent implementation (e.g. `pip install kyber-py`) and the official NIST ACVP ML-KEM test vectors (usnistgov ACVP-Server repo; find and cite the exact files) for 512 and 768.
2. **`sim/pins.py`:** a per-clock pin frame `(ui_in, uio_in) -> (uo_out, uio_out, uio_oe)`.
3. **`sim/chip_a.py`, `sim/chip_b.py`:** cycle-accurate behavioural models of each chip at pin level. Each has `step(ui_in, uio_in) -> uo_out` per clock, with internal state, B's shuffle LFSR and a serial/parallel multiplier parameter.
4. **`sim/host.py`:** RP2350 driver model. It turns `ntt / intt / basemul / scale` calls into per-clock stimulus lists, runs them through a chip model, samples outputs at the fixed offsets and decodes ByteEncode12. Plus `docs/PROTOCOL.md`, which freezes the exact latencies and frame formats; the RTL must later match them **cycle-exactly**.
    - ✅ ML-KEM-512 and -768 KeyGen/Encaps/Decaps with `backend = chip_a` and `chip_b` give **byte-identical** keys, ciphertexts and shared keys to the reference, over ≥100 random seeds.
    - ✅ Cycle counts per NTT match section 4: A 2,688, B1 3,968, B2 2,176, plus a small fixed latency. Explain any difference.
    - ✅ Constant-time test passes (section 5).
5. **`sim/report.py`:** the bottleneck tables from section 6, written to `reports/`.
6. **Stimulus export:** the same per-clock stimulus as files of 16-bit words `{uio_in, ui_in}`, plus expected `uo_out` per clock. Stages 2–5 (cocotb and the Tang Nano vector player) replay exactly these files.

### Stage 2: logic blocks for A, one at a time (Verilog in `src/`, cocotb in `test/`)

Order:
1. Twiddle ROM (all 128 entries).
2. Barrett + modular multiplier: exhaustive or ≥1M random against the model.
3. CT/GS butterfly.
4. Packer.
5. Sequencer.
6. Basemul/scale control.
7. A's `tt_um_*` top.

- ✅ Each block bit-exact against the Python functions.
- ✅ The A top replays the stage-1 stimulus files with **cycle-exact** `uo_out`.
- ✅ The synthesized area of each block is logged next to the table in section 4.

### Stage 3: B's extra blocks

Order:
1. 16 × 12 buffer.
2. Address generator, checked against `b_pair` / `b_zidx` for every pass, layer and k.
3. Shuffle LFSR.
4. Block FSM.
5. B top, keeping stream mode.

- ✅ Cycle-exact against `chip_b.py` stimulus, with shuffle on and off.
- ✅ Area within the 2×2 budget.

### Stage 4: full ML-KEM through the RTL

`mlkem.py` uses a cocotb-driven RTL backend.

- ✅ One full KeyGen/Encaps/Decaps per design matches the reference bytes.

### Stage 5: Tang Nano 20K

Follow `HANDOFF_tang_nano_emulator.md`. The PC streams the stage-1 stimulus files over UART into the FPGA and compares the captures.

## 8. Rules

1. `src/` is pure portable Verilog:
    - no vendor primitives
    - no `initial` blocks
    - every register reset
    - one shared twiddle ROM; synthesis showed that calling the ROM function 3–4 times duplicates it
2. Python is the source of truth. When the RTL and the model disagree, find out which one is wrong. **Never edit the golden model to make a test pass** without telling me why.
3. The template's GitHub Actions (test, docs, GDS) must stay green.
4. Python ≥ 3.10, `pytest` for all Python tests, and no network at test time. Vendor the test vectors into `test/vectors/`.
5. Mark every number you didn't measure or look up as an assumption. When a fact is uncertain (a pin, a tool flag, a TT limit), say so instead of guessing.

## 9. Open decisions (ask me, don't decide alone)

- The `tt_um_*` module name.
- Serial or parallel multiplier in B. Parallel costs ~1,700 µm² (~2% of a 2×2) and gives 3,968 → 2,176 clocks.
- Whether to attempt B3 (overlapped buffers) if the 2×2 still has room.
- The exact latency constants. You propose them in `docs/PROTOCOL.md`, and I approve.
