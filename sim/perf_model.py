"""Performance prediction: turn what we measure (Python on the PC, the chip on the FPGA over USB) into what
the proposed system would do (RP2350 alone, RP2350 + our chip on the Tiny Tapeout board).

Three coefficients, each a ratio of a prediction to a measurement of the same part:

  K_py   = RP2350 software time / Python-only time            (whole ML-KEM operation)
  K_host = RP2350 host-side time / Python host-side time      (everything except the chip calls)
  K_chip = chip time on silicon / chip time on the FPGA       (the chip calls, including USB)

so  predicted RP2350 alone      = measured Python-only           x K_py
    predicted RP2350 + our chip = measured host part x K_host + measured FPGA chip part x K_chip

What goes into the predictions (all in sim/config.py, each marked cited / measured / ASSUMPTION):
  RP2350 software:  pqm4 m4fspeed cycles (cited) / f_rp, Cortex-M33 ~ Cortex-M4 (assumption)
  RP2350 host part: pqm4 cycles minus the cited software cost of the offloaded calls (ePrint 2022/112)
  chip calls:       exact protocol clocks per call (from the RTL-matched model) / f_chip, where f_chip is
                    limited by the timing target, the measured STA and the I/O and PIO limits, plus the
                    RP2350's packing/unpacking per unit in one of three transfer scenarios (SCENARIOS):
                    CPU-serial, PIO+DMA double-buffered, PIO+DMA on both cores. The pins move one word
                    per chip clock in all of them, so the protocol stream is the floor.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "model")]

from config import PARAMS, PQM4, p  # noqa: E402

OPS_768 = {"keygen": ("ML-KEM-768", "keygen"), "encaps": ("ML-KEM-768", "encaps"), "decaps": ("ML-KEM-768", "decaps")}

# protocol clocks per call (continuous streaming, verified cycle-exact on RTL and FPGA): forward/inverse
# 895*3 + D + 3, basemul 127*15 + 20 + 3, scale 127*6 + 9 + 3
CLOCKS_PER_CALL = {"ntt": 2694, "invntt": 2695, "basemul": 1928, "scale": 774}
UNITS_PER_CALL = {"ntt": 896, "invntt": 896, "basemul": 128, "scale": 128}


def f_chip(corner="nominal"):
    """Chip clock the system can actually use: the lowest of all limits."""
    limits = {
        "timing target": p("f_chip_target_hz"),
        "I/O limit": p("f_io_limit_hz"),
        "PIO lockstep": p("f_rp_hz") / p("pio_cycles_per_chip_clock"),
        "STA": p("f_chip_sta_typ_hz") if corner == "nominal" else p("f_chip_sta_slow_hz"),
    }
    name = min(limits, key=limits.get)
    return limits[name], name, limits


def rp2350_sw_s(ps, op):
    cycles, _ = PQM4[(ps, op)]
    return cycles * p("m33_vs_m4") / p("f_rp_hz")


def rp2350_host_s(ps, op, calls):
    """RP2350 work the chip never touches: pqm4 total minus the cited software cost of the offloaded calls."""
    cycles, _ = PQM4[(ps, op)]
    off = calls.get("ntt", 0) * p("sw_ntt") + calls.get("invntt", 0) * p("sw_invntt") + calls.get("basemul", 0) * p("sw_basemul")
    return (cycles - off) * p("m33_vs_m4") / p("f_rp_hz")


SCENARIOS = {
    "cpu_serial":    "CPU packs/unpacks, then waits for each transfer (no overlap)",
    "pio_dma":       "PIO lockstep + DMA, double-buffered: CPU work overlaps the streaming (1 core)",
    "pio_dma_2core": "as pio_dma, with packing and unpacking split over both M33 cores",
}
DEFAULT_SCENARIO = "pio_dma"


def _cpu_cycles_per_unit(op, scenario):
    if scenario == "cpu_serial":
        return p("cpu_serial_cyc_bf") if op in ("ntt", "invntt") else p("book_per_transaction")
    c = {"ntt": p("pio_dma_cyc_bf"), "invntt": p("pio_dma_cyc_bf"), "basemul": p("pio_dma_cyc_piece"),
         "scale": p("pio_dma_cyc_scale")}[op]
    return c / p("cores") if scenario == "pio_dma_2core" else c


def chip_call_breakdown(op, n=1, scenario=DEFAULT_SCENARIO, corner="nominal"):
    """One kind of chip call on the TT board, n times. Every part includes moving the bits over the pins:
         pins_s  : the protocol stream itself (inputs in, result bytes out, one word per chip clock)
         cpu_s   : RP2350 packing/unpacking/index math
         total_s : what the call costs the system (overlapped or not, + setup)"""
    f, _, _ = f_chip(corner)
    pins = CLOCKS_PER_CALL[op] / f
    cpu = UNITS_PER_CALL[op] * _cpu_cycles_per_unit(op, scenario) / p("f_rp_hz")
    setup = p("setup_cycles_per_call") / p("f_rp_hz")
    if scenario == "cpu_serial":
        total = pins + cpu + setup
    else:   # double-buffered: the slower of stream and CPU, plus pipeline fill (16 units) and setup
        total = max(pins, cpu) + 16 * _cpu_cycles_per_unit(op, scenario) / p("f_rp_hz") + setup
    return {"pins_s": n * pins, "cpu_s": n * cpu, "total_s": n * total, "bound": "pins" if pins >= cpu else "CPU"}


def chip_calls_s(calls, corner="nominal", scenario=DEFAULT_SCENARIO):
    """Time of all chip calls on the TT board, including the pin transfers."""
    return sum(chip_call_breakdown(op, n, scenario, corner)["total_s"] for op, n in calls.items() if n)


# what crosses the pins and what the chip computes, per call (exact, from the protocol and the RTL)
WORDS_IN = {"ntt": 1792, "invntt": 1792, "basemul": 512, "scale": 256}      # 1 word per chip clock
BYTES_OUT = {"ntt": 2688, "invntt": 2688, "basemul": 384, "scale": 384}     # 1 byte per chip clock
MULT_PRODUCTS = {"ntt": 896, "invntt": 896, "basemul": 640, "scale": 256}   # modq_mul: 1 product / 3 clocks
SW_KEY = {"ntt": "sw_ntt", "invntt": "sw_invntt", "basemul": "sw_basemul", "scale": None}


def silicon_breakdown(op, corner="nominal"):
    """One chip call on the TT board, split into its parts. Each part as if it ran alone:
         tx_s    : input words over the 16 input pins (1 word / clock)
         calc_s  : the chip's own arithmetic: multiplier busy time, as if the data were already inside
         rx_s    : result bytes over the 8 output pins (1 byte / clock)
       and what really happens:
         wall_s  : the protocol overlaps all three; this is the measured-on-RTL clock count
         pack_s / unpack_s : RP2350 CPU work to feed / drain the PIO FIFOs with DMA
         rp_sw_s : the same operation done by the RP2350 alone in software (cited cycles; scale is inside iNTT)"""
    f, _, _ = f_chip(corner)
    rp = p("f_rp_hz")
    kind = {"ntt": "bf", "invntt": "bf", "basemul": "piece", "scale": "scale"}[op]
    sw = SW_KEY[op]
    return {
        "tx_s": WORDS_IN[op] / f,
        "calc_s": MULT_PRODUCTS[op] * 3 / f,
        "rx_s": BYTES_OUT[op] / f,
        "wall_s": CLOCKS_PER_CALL[op] / f,
        "pack_s": UNITS_PER_CALL[op] * p(f"pack_cyc_{kind}") / rp,
        "unpack_s": UNITS_PER_CALL[op] * p(f"unpack_cyc_{kind}") / rp,
        "rp_sw_s": p(sw) * p("m33_vs_m4") / rp if sw else None,
        "calc_parallel_s": MULT_PRODUCTS[op] / f,      # what-if: a 12x12 parallel multiplier, 1 product / clock
        "bound": _bound(op),
    }


def _bound(op):
    parts = {"TX pins": WORDS_IN[op], "chip calc": MULT_PRODUCTS[op] * 3, "RX pins": BYTES_OUT[op]}
    top = max(parts.values())
    return " = ".join(k for k, v in parts.items() if v == top)


def sw_offloaded_s(calls):
    """What the offloaded calls cost the RP2350 in software (cited, ePrint 2022/112; scale is inside its iNTT)."""
    cyc = calls.get("ntt", 0) * p("sw_ntt") + calls.get("invntt", 0) * p("sw_invntt") + calls.get("basemul", 0) * p("sw_basemul")
    return cyc * p("m33_vs_m4") / p("f_rp_hz")


def chip_part(calls, py_chip_s=None, fpga_chip_s=None, corner="nominal"):
    """Only the part the chip does (NTT, INTT, basemul, scale), every way we can run or predict it."""
    f, lim, _ = f_chip(corner)
    pins = sum(chip_call_breakdown(op, n, "pio_dma", corner)["pins_s"] for op, n in calls.items() if n)
    out = {"python_pc_s": py_chip_s, "fpga_usb_s": fpga_chip_s, "rp2350_sw_s": sw_offloaded_s(calls),
           "silicon_pins_only_s": pins, "f_chip_hz": f, "f_chip_limited_by": lim}
    for sc in SCENARIOS:
        out[f"rp2350_chip_{sc}_s"] = chip_calls_s(calls, corner, sc)
    return out


def predict(op, py_only_s, fpga_host_s, fpga_chip_s, calls, corner="nominal", scenario=DEFAULT_SCENARIO):
    """All numbers for one ML-KEM-768 operation. calls: {'ntt': n, 'invntt': n, 'basemul': n, 'scale': n}."""
    ps, o = OPS_768[op]
    t_sw = rp2350_sw_s(ps, o)
    t_host = rp2350_host_s(ps, o, calls)
    t_chip = chip_calls_s(calls, corner, scenario)
    return {
        "measured": {"python_only_s": py_only_s, "fpga_host_s": fpga_host_s, "fpga_chip_s": fpga_chip_s,
                     "fpga_total_s": fpga_host_s + fpga_chip_s},
        "coefficients": {"K_py": t_sw / py_only_s if py_only_s else None,
                         "K_host": t_host / fpga_host_s if fpga_host_s else None,
                         "K_chip": t_chip / fpga_chip_s if fpga_chip_s else None},
        "predicted": {"rp2350_alone_s": t_sw, "rp2350_host_s": t_host, "chip_calls_s": t_chip,
                      "rp2350_plus_chip_s": t_host + t_chip, "speedup_vs_rp2350": t_sw / (t_host + t_chip)},
        "f_chip_hz": f_chip(corner)[0], "f_chip_limited_by": f_chip(corner)[1], "corner": corner,
        "scenario": scenario,
    }


def assumptions():
    """(name, value, status) for every parameter a prediction uses, for display next to the numbers."""
    keys = ["f_rp_hz", "m33_vs_m4", "pio_cycles_per_chip_clock", "book_per_butterfly", "book_per_transaction",
            "book_overlap", "sw_ntt", "sw_invntt", "sw_basemul", "f_chip_target_hz", "f_chip_sta_typ_hz",
            "f_chip_sta_slow_hz", "f_io_limit_hz", "setup_cycles_per_call", "cpu_serial_cyc_bf", "pio_dma_cyc_bf",
            "pio_dma_cyc_piece", "pio_dma_cyc_scale", "cores", "pack_cyc_bf", "unpack_cyc_bf", "pack_cyc_piece",
            "unpack_cyc_piece", "pack_cyc_scale", "unpack_cyc_scale"]
    return [(k, PARAMS[k][0], PARAMS[k][1]) for k in keys]
