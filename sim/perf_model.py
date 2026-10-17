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
                    limited by the timing target, the measured STA and the I/O and PIO limits, plus host
                    bookkeeping per butterfly / basemul piece (assumption)
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


def chip_calls_s(calls, corner="nominal"):
    """Time of the chip calls on the TT board: protocol clocks / f_chip + RP2350 bookkeeping per unit."""
    f, _, _ = f_chip(corner)
    t = 0.0
    for op, n in calls.items():
        book = p("book_per_butterfly") if op in ("ntt", "invntt") else p("book_per_transaction")
        t += n * (CLOCKS_PER_CALL[op] / f + UNITS_PER_CALL[op] * book / p("f_rp_hz") * (1 - p("book_overlap")))
    return t


def predict(op, py_only_s, fpga_host_s, fpga_chip_s, calls, corner="nominal"):
    """All numbers for one ML-KEM-768 operation. calls: {'ntt': n, 'invntt': n, 'basemul': n, 'scale': n}."""
    ps, o = OPS_768[op]
    t_sw = rp2350_sw_s(ps, o)
    t_host = rp2350_host_s(ps, o, calls)
    t_chip = chip_calls_s(calls, corner)
    return {
        "measured": {"python_only_s": py_only_s, "fpga_host_s": fpga_host_s, "fpga_chip_s": fpga_chip_s,
                     "fpga_total_s": fpga_host_s + fpga_chip_s},
        "coefficients": {"K_py": t_sw / py_only_s if py_only_s else None,
                         "K_host": t_host / fpga_host_s if fpga_host_s else None,
                         "K_chip": t_chip / fpga_chip_s if fpga_chip_s else None},
        "predicted": {"rp2350_alone_s": t_sw, "rp2350_host_s": t_host, "chip_calls_s": t_chip,
                      "rp2350_plus_chip_s": t_host + t_chip, "speedup_vs_rp2350": t_sw / (t_host + t_chip)},
        "f_chip_hz": f_chip(corner)[0], "f_chip_limited_by": f_chip(corner)[1], "corner": corner,
    }


def assumptions():
    """(name, value, status) for every parameter a prediction uses, for display next to the numbers."""
    keys = ["f_rp_hz", "m33_vs_m4", "pio_cycles_per_chip_clock", "book_per_butterfly", "book_per_transaction",
            "book_overlap", "sw_ntt", "sw_invntt", "sw_basemul", "f_chip_target_hz", "f_chip_sta_typ_hz",
            "f_chip_sta_slow_hz", "f_io_limit_hz"]
    return [(k, PARAMS[k][0], PARAMS[k][1]) for k in keys]
