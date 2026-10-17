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

    # chip clock limits (prediction coefficient inputs)
    "f_chip_target_hz":     (50e6, "cited: src/config.json CLOCK_PERIOD = 20 ns (the TT flow's timing target)"),
    "f_chip_sta_typ_hz":    (1 / (20e-9 - 8.501e-9), "measured: local LibreLane STA, typical corner, 8.5 ns slack at 20 ns -> 87 MHz"),
    "f_chip_sta_slow_hz":   (1 / (20e-9 + 2.309e-9), "measured: local LibreLane STA, ss 100C 1.60 V, -2.31 ns slack -> 44.8 MHz"),
    "f_io_limit_hz":        (50e6, "ASSUMPTION: TT mux/pad/demo-board limit for a lockstep bus; not confirmed"),

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
