"""Every host/system parameter of the bottleneck report, in one place.

Each entry is (value, status). Status is one of:
  "cited"       - looked up, source given in SOURCES
  "simulated"   - comes from sim/ (filled in by report.py, not here)
  "ASSUMPTION"  - a guess until measured on hardware. Replace with measurements (Pico 2 + chip/FPGA).
"""

F_CHIP_SWEEP_HZ = ([10e6, 25e6, 50e6],
                   "ASSUMPTION: 50 MHz is the default timing target in src/config.json (CLOCK_PERIOD 20 ns); "
                   "the real limit through the TT mux, pads and demo board is not confirmed")

PARAMS = {
    # host
    "f_rp_hz":               (150e6, "ASSUMPTION (RP2350 default clock, per handoff)"),
    "m33_vs_m4":             (1.0,   "ASSUMPTION: Cortex-M33 cycles = Cortex-M4 cycles for this code"),

    # transfer modes
    "pio_cycles_per_chip_clock": (2, "ASSUMPTION: PIO program needs 2 instructions per chip clock "
                                     "(drive + sample), so lockstep needs f_chip <= f_rp / 2"),
    "fifo_cpu_cycles_per_word":  (6, "ASSUMPTION: CPU cycles to push one 16-bit input word into the PIO TX FIFO"),
    "fifo_cpu_cycles_per_byte":  (6, "ASSUMPTION: CPU cycles to pop one result byte from the PIO RX FIFO"),
    "fifo_depth":                (8, "ASSUMPTION: RP2350 PIO FIFO depth with join (4 without)"),
    "bitbang_cycles_per_clock":  (12, "ASSUMPTION: CPU cycles per chip clock with SIO GPIO "
                                      "(write pins, clock high, read uo_out, clock low)"),

    # host bookkeeping, CPU cycles
    "book_per_butterfly":   (20, "ASSUMPTION: design A, index math + unpack 3 bytes + write back 2 coeffs"),
    "book_per_transaction": (20, "ASSUMPTION: basemul / scale stream transaction"),
    "book_per_block":       (160, "ASSUMPTION: design B, gather 16 + scatter 16 coefficients"),
    "book_overlap":         (0.0, "ASSUMPTION: fraction of bookkeeping hidden behind the stream "
                                  "(0 = none; DMA-driven PIO could raise it)"),

    # software baseline and the host work the chip never touches
    # software cost of the offloaded ops (Cortex-M4 cycles, speed-optimized), cited: ePrint 2022/112 Table 2
    "sw_ntt":               (5992, "cited: ePrint 2022/112 Table 2, Kyber NTT, 'This work'"),
    "sw_invntt":            (5491, "cited: ePrint 2022/112 Table 2, Kyber iNTT (speed), includes the x128^-1 scale"),
    "sw_basemul":           (1613, "cited: ePrint 2022/112 Table 2, Kyber basemul (asymmetric, as in the inner product)"),

    # RP2350 <-> chip transfer scenarios (CPU cycles per protocol unit: pack the input words, unpack the
    # 3 result bytes, index math). The pins themselves move one word per chip clock in every scenario.
    "setup_cycles_per_call": (300, "ASSUMPTION: DMA/PIO setup and job start per chip call"),
    "cpu_serial_cyc_bf":     (20, "ASSUMPTION (conservative): plain C loop, CPU waits for each layer's transfer"),
    "pio_dma_cyc_bf":        (12, "ASSUMPTION: ldr/orr/str of 2 words into the PIO TX buffer + ubfx unpack of one "
                                  "24-bit autopushed result + loop index math, overlapped with DMA streaming"),
    "pio_dma_cyc_piece":     (14, "ASSUMPTION: basemul piece, 4 words in + 1 result"),
    "pio_dma_cyc_scale":     (8,  "ASSUMPTION: scale pair, 2 words in + 1 result"),
    "cores":                 (2,  "cited: the RP2350 has two Cortex-M33 cores (the 2-core scenario splits pack and unpack)"),
    # how the PIO+DMA CPU cycles above split into packing (TX side) and unpacking (RX side)
    "pack_cyc_bf":      (6,  "ASSUMPTION: 2 coefficient loads, OR in valid/op bits, one 32-bit store to the TX buffer"),
    "unpack_cyc_bf":    (6,  "ASSUMPTION: one 32-bit load of the autopushed 3 bytes, 2 bitfield extracts, 2 stores"),
    "pack_cyc_piece":   (10, "ASSUMPTION: basemul piece, 4 coefficient loads + 2 stores"),
    "unpack_cyc_piece": (4,  "ASSUMPTION: basemul piece, one result pair"),
    "pack_cyc_scale":   (5,  "ASSUMPTION: scale pair, 2 coefficient loads + 2 stores"),
    "unpack_cyc_scale": (3,  "ASSUMPTION: scale pair, one result pair"),

    # chip clock limits (prediction coefficient inputs)
    "f_chip_target_hz":     (50e6, "cited: src/config.json CLOCK_PERIOD = 20 ns (the TT flow's timing target)"),
    "f_chip_sta_typ_hz":    (1 / (20e-9 - 10.464e-9), "measured: team chip tt_um_NTT_Core at acff283 (timing-closure fixes), "
                                                      "local TT-flow harden, typical corner, +10.46 ns slack at 20 ns -> 105 MHz"),
    "f_chip_sta_slow_hz":   (1 / (20e-9 - 1.407e-9), "measured: same harden, ss 100C 1.60 V, +1.41 ns slack -> 53.8 MHz "
                                                    "(matches the team's own post-PnR figure)"),
    "f_io_limit_hz":        (50e6, "ASSUMPTION: TT mux/pad/demo-board limit for a lockstep bus; not confirmed"),

    # The RP2350 firmware as written (chipathon-2026 rp2350/core/ntt_chip.c): per batch (an NTT layer, a basemul
    # or a scale job) it builds the input words, streams them through PIO + DMA, then unpacks the results, one
    # after the other. CPU cycles, estimated from its loops compiled for the Cortex-M33 (arm-none-eabi-gcc 14.2 -O2;
    # ~1 cycle per instruction, +1 per load and taken branch). tools/rp_log.py replaces them with values fitted to
    # the firmware's own timing log (perf/rp_coeffs.json) once the Pico 2 W + Tang Nano rig runs.
    "fw_prep_cyc_input":  (22, "ESTIMATE: run_units word-building loop, 17 instructions per input coefficient"),
    "fw_prep_cyc_word":   (1.0, "ESTIMATE: memset of the word buffer (idle clocks), per chip clock"),
    "fw_post_cyc_pair":   (45, "ESTIMATE: unpack loop, 22 instructions per result pair + unpack_pair (12 + call)"),
    "fw_gather_cyc_unit": (18, "ESTIMATE: ntt_job gather and scatter loops, 6 instructions each per butterfly "
                               "(NTT jobs only)"),
    "fw_batch_cyc":       (500, "ESTIMATE: per batch: two DMA channel set-ups, a 64-bit timeout division, completion "
                                "polling, four timestamps and a log record"),
    "fw_call_cyc":        (400, "ESTIMATE: per call: two 512-byte memcpy, entry and exit, a log record"),

    # design B3 (overlapped buffers) is not built: handoff estimate
    "b3_ntt_clocks":        (950, "ASSUMPTION: handoff estimate ~900-1,000 clocks per NTT/INTT; B3 not simulated"),
}

# pqm4 m4fspeed, cycles on Cortex-M4 (STM32F407), and hashing share of those cycles
PQM4 = {
    ("ML-KEM-512", "keygen"): (392_423, 0.755), ("ML-KEM-512", "encaps"): (390_881, 0.735),
    ("ML-KEM-512", "decaps"): (428_167, 0.671), ("ML-KEM-768", "keygen"): (642_096, 0.745),
    ("ML-KEM-768", "encaps"): (658_754, 0.744), ("ML-KEM-768", "decaps"): (707_827, 0.692),
}

SOURCES = {
    "eprint2022_112": "A. Abdulrahman, V. Hwang, M. J. Kannwischer, A. Sprenkels, 'Faster Kyber and Dilithium on "
                      "the Cortex-M4', ACNS 2022, ePrint 2022/112, Table 2 (copy in ref-docs/2022-112.pdf)",
    "pqm4": "mupq/pqm4 benchmarks.md, commit 5e5cc76d0b072ee7077e58afcbc619a1a67a53b4: "
            "'Speed Evaluation' (m4fspeed, AVG cycles) and 'Hashing Evaluation' tables, "
            "https://github.com/mupq/pqm4/blob/5e5cc76d0b072ee7077e58afcbc619a1a67a53b4/benchmarks.md",
}


def p(name):
    return PARAMS[name][0]
