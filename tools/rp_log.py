"""The RP2350 firmware's operation timing log -> measured firmware coefficients for sim/perf_model.py.

The firmware (chipathon-2026 rp2350/, TT_TARGET=pico2w_tang on the Pico 2 W + Tang Nano rig, or dbv3 on the
TT demo board) times every chip batch and call in CPU cycles (core/oplog.h). This tool runs a benchmark on it,
reads the log as CSV, fits the per-coefficient / per-pair / per-batch / per-call costs that sim/perf_model.py
uses for the "rp_fw" scenario, and saves them to perf/rp_coeffs.json. From then on every prediction (website,
tools/perf.py, sim/arch_explore.py) uses the measured values instead of the estimates.

    python3 tools/rp_log.py capture --port /dev/ttyACM0 [--n 20] [--clk 10000000]   # run, fit, save
    python3 tools/rp_log.py fit perf/rp_log/<file>.csv [--save]                     # refit a saved log
    python3 tools/rp_log.py show                                                   # current coefficients + predictions

Only the CPU parts are fitted. The chip's streaming time is never taken from the rig: it is clocks / f, with
the clocks exact from the protocol, so the rig's slower clock and longer wires don't leak into the prediction.
"""
import argparse
import csv
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "model")]

LOG_DIR = os.path.join(ROOT, "perf", "rp_log")
COEFFS = os.path.join(ROOT, "perf", "rp_coeffs.json")
PERF_LOG = os.path.join(ROOT, "perf", "perf_log.jsonl")
N_IN = {"forward": 2, "inverse": 2, "basemul": 4, "scale": 2}
OP_KEY = {"forward": "ntt", "inverse": "invntt", "basemul": "basemul", "scale": "scale"}


# ---------------- capture ----------------
def command(ser, line, timeout):
    """Send one text command and return its output (the firmware ends every reply with the "> " prompt)."""
    ser.reset_input_buffer()
    ser.write((line + "\r").encode())
    buf, last = b"", time.time()
    while time.time() - last < timeout:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk
            last = time.time()
            if buf.endswith(b"> "):
                break
    return buf.decode(errors="replace").replace("\r", "")


def capture(port, n, clk):
    import serial
    ser = serial.Serial(port, 115200, timeout=0.2)
    time.sleep(0.2)
    print(command(ser, "status", 2).strip())
    if clk:
        print(command(ser, f"clk {clk}", 2).strip())
    out = command(ser, f"bench {n}", 120)
    print(out.strip())
    text = command(ser, "log csv", 30)
    rows = [ln for ln in text.splitlines() if ln.startswith(("kind,", "batch,", "call,"))]
    if len(rows) < 2:
        raise SystemExit("no log records came back: is this the RP2350 firmware with the oplog (help lists `log`)?")
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, time.strftime("%Y%m%d-%H%M%S") + ".csv")
    with open(path, "w") as fh:
        fh.write("\n".join(rows) + "\n")
    print(f"saved {len(rows) - 1} records to {os.path.relpath(path, ROOT)}")
    return path


# ---------------- fit ----------------
def read_log(path):
    with open(path) as fh:
        recs = list(csv.DictReader(fh))
    for r in recs:
        for k in ("batch", "units", "words", "prep_cyc", "run_cyc", "conv_cyc", "post_cyc", "total_cyc", "chip_hz",
                  "cpu_hz", "skew"):
            r[k] = int(r[k])
    return recs


def lstsq2(xs, ys):
    """y = a * x0 + b * x1, least squares (two unknowns, closed form)."""
    s00 = sum(x[0] * x[0] for x in xs)
    s01 = sum(x[0] * x[1] for x in xs)
    s11 = sum(x[1] * x[1] for x in xs)
    t0 = sum(x[0] * y for x, y in zip(xs, ys))
    t1 = sum(x[1] * y for x, y in zip(xs, ys))
    det = s00 * s11 - s01 * s01
    if abs(det) < 1e-9:
        return t0 / s00 if s00 else 0.0, 0.0
    return (t0 * s11 - t1 * s01) / det, (t1 * s00 - t0 * s01) / det


def fit(recs):
    """Fit the firmware costs (CPU cycles) of sim/config.py's fw_* parameters to a log."""
    batches, calls, pending = [], [], []
    for r in recs:
        if r["kind"] == "batch":
            pending.append(r)
        else:
            calls.append((r, pending))
            pending = []
            batches += calls[-1][1]
    if not calls:
        raise ValueError("the log has no complete call")
    cpu_hz = recs[0]["cpu_hz"]
    # prep = a * input coefficients + b * words (the word buffer is cleared, then filled)
    a, b = lstsq2([(r["units"] * N_IN[r["op"]], r["words"]) for r in batches], [r["prep_cyc"] for r in batches])
    post = sum(r["post_cyc"] for r in batches) / sum(r["units"] for r in batches)
    ovh = []
    for r in batches:
        if r["chip_hz"]:
            ovh.append(max(0.0, r["run_cyc"] - r["conv_cyc"] - r["words"] * cpu_hz / r["chip_hz"]))
    batch = sum(ovh) / len(ovh) if ovh else 0.0
    other_single = [c["total_cyc"] - sum(b_["prep_cyc"] + b_["run_cyc"] + b_["post_cyc"] for b_ in bs)
                    for c, bs in calls if c["op"] in ("basemul", "scale")]
    other_ntt = [c["total_cyc"] - sum(b_["prep_cyc"] + b_["run_cyc"] + b_["post_cyc"] for b_ in bs)
                 for c, bs in calls if c["op"] in ("forward", "inverse")]
    call = sum(other_single) / len(other_single) if other_single else 0.0
    gather = (sum(other_ntt) / len(other_ntt) - call) / 896 if other_ntt else 0.0
    conv = sum(r["conv_cyc"] for r in batches) / max(1, sum(r["words"] for r in batches))
    coeffs = {"fw_prep_cyc_input": round(a, 2), "fw_prep_cyc_word": round(b, 3), "fw_post_cyc_pair": round(post, 2),
              "fw_gather_cyc_unit": round(max(gather, 0.0), 2), "fw_batch_cyc": round(batch, 1),
              "fw_call_cyc": round(max(call, 0.0), 1)}
    info = {"cpu_hz": cpu_hz, "chip_hz": sorted({r["chip_hz"] for r in batches}), "batches": len(batches),
            "calls": len(calls), "rig_conv_cyc_per_word": round(conv, 3)}
    return coeffs, info


def report(coeffs=None):
    import importlib
    import perf_model as PM
    importlib.reload(PM)
    c = PM.fw_coeffs()
    print("firmware coefficients (CPU cycles):")
    for k, (v, s) in c.items():
        mark = " <- new" if coeffs and k in coeffs else ""
        print(f"  {k:20} {v:9.2f}  {s}{mark}")
    f = PM.f_chip()[0]
    print(f"\nper call on the TT board at {f / 1e6:.0f} MHz (firmware as written):")
    for op in PM.CLOCKS_PER_CALL:
        fw = PM.fw_call_parts(op, f)
        print(f"  {op:8} {fw['total_s'] * 1e6:8.1f} us = chip stream {fw['stream_s'] * 1e6:6.1f} + CPU "
              f"{fw['cpu_s'] * 1e6:7.1f} (prep {fw['prep_s'] * 1e6:.1f}, post {fw['post_s'] * 1e6:.1f}, "
              f"other {fw['other_s'] * 1e6:.1f}, transfer set-up {fw['overhead_s'] * 1e6:.1f})")
    return PM


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--port", required=True)
    c.add_argument("--n", type=int, default=20, help="calls per mode in the benchmark")
    c.add_argument("--clk", type=int, help="set the chip clock first (Hz)")
    f = sub.add_parser("fit")
    f.add_argument("csv")
    f.add_argument("--save", action="store_true", help="write perf/rp_coeffs.json (RP2350 logs only)")
    sub.add_parser("show")
    a = ap.parse_args()
    if a.cmd == "show":
        report()
        return
    path = capture(a.port, a.n, a.clk) if a.cmd == "capture" else a.csv
    coeffs, info = fit(read_log(path))
    print(f"\nfitted from {info['batches']} batches, {info['calls']} calls; CPU {info['cpu_hz'] / 1e6:.0f} MHz, "
          f"chip clock {info['chip_hz']}; rig word conversion {info['rig_conv_cyc_per_word']} cycles/word (dropped)")
    save = a.cmd == "capture" or a.save
    if save and info["cpu_hz"] > 400e6:
        print("this log is from a PC (cycle counter in ns), not an RP2350: not saved")
        save = False
    if save:
        rec = {"coeffs": coeffs, "source": f"{os.path.relpath(path, ROOT)}, {time.strftime('%Y-%m-%d')}",
               "info": info}
        with open(COEFFS, "w") as fh:
            json.dump(rec, fh, indent=1)
        print(f"saved {os.path.relpath(COEFFS, ROOT)}")
    PM = report(coeffs if save else None)
    if save:
        pred = {op: PM.fw_call_parts(op)["total_s"] for op in PM.CLOCKS_PER_CALL}
        with open(PERF_LOG, "a") as fh:
            fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "measured-rp",
                                 "source": rec["source"], "coeffs": coeffs, "info": info,
                                 "predicted_call_s_at_f_chip": pred}) + "\n")
    elif a.cmd == "fit":
        print("\n(not saved; the coefficients above are the current ones)")
        for k, v in coeffs.items():
            print(f"  fitted {k:20} {v}")


if __name__ == "__main__":
    main()
