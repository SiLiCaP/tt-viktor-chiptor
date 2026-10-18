"""How long each local harden (GDS + signoff) took, stage by stage, from LibreLane's per-step runtime.txt.

    python3 tools/harden_times.py                 # every tools/tile_exp.py run in ~/tools/work/exp
    python3 tools/harden_times.py DIR [DIR ...]   # any design folders with runs/wokwi

Stages group LibreLane's steps: lint + synthesis, floorplan + PDN, placement, CTS + timing repair, routing
(global, antenna repair, detailed), signoff (RC extraction, STA, magic / KLayout stream-out, DRC, LVS and the
checkers). "wall" is the whole tt_tool --harden call as tile_exp timed it (includes container start-up).
"""
import json
import os
import re
import sys

WORK = os.path.expanduser("~/tools/work/exp")
STAGES = [
    ("synth", ("verilator", "lint", "yosys", "checker-yosys", "netlistassign", "checksdc", "checkmacro", "staprepnr")),
    ("floorplan", ("floorplan", "dumprc", "macro", "powerconn", "cutrows", "tapendcap", "pdn", "obstructions")),
    ("place", ("placement", "ioplacement", "deftemplate", "verilogheader", "powergrid", "repairdesignpostgpl",
               "stamidpnr")),
    ("cts", ("cts", "resizertimingpostcts")),
    ("route", ("globalrouting", "antennas", "diodes", "detailedrouting", "routingobstructions", "trdrc",
               "disconnected", "wirelength", "resizertimingpostgrt")),
    ("signoff", ("fill", "cellfrequency", "rcx", "stapostpnr", "irdrop", "streamout", "render", "writelef",
                 "antennaproperties", "drc", "spice", "overlap", "lvs", "violations", "manufacturability")),
]


def secs(txt):
    h, m, s = txt.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def stage_of(step):
    name = step.split("-", 1)[1]
    for st, keys in STAGES:
        if any(k in name for k in keys):
            return st
    return "signoff"


def times(d):
    runs = os.path.join(d, "runs", "wokwi")
    out = {st: 0.0 for st, _ in STAGES}
    last = None
    if not os.path.isdir(runs):
        return None
    for step in sorted((s for s in os.listdir(runs) if re.match(r"\d+-", s)), key=lambda s: int(s.split("-")[0])):
        rt = os.path.join(runs, step, "runtime.txt")
        if os.path.exists(rt):
            out[stage_of(step)] += secs(open(rt).read())
        last = step
    out["last"] = last
    out["done"] = os.path.exists(os.path.join(runs, "final", "metrics.json"))
    return out


def main():
    dirs = sys.argv[1:] or sorted(os.path.join(WORK, n) for n in os.listdir(WORK)
                                  if os.path.isdir(os.path.join(WORK, n, "runs")))
    print(f"{'run':16} {'synth':>6} {'flplan':>6} {'place':>6} {'cts':>6} {'route':>7} {'signoff':>7} "
          f"{'steps':>7} {'wall':>6}  result")
    for d in dirs:
        t = times(d)
        if not t:
            continue
        res = os.path.join(d, "result.json")
        rec = json.load(open(res)) if os.path.exists(res) else {}
        wall = rec.get("harden_min")
        total = sum(t[st] for st, _ in STAGES)
        m = lambda s: f"{s / 60:5.1f}m"
        state = "done" if t["done"] else f"stopped at {t['last']}"
        if rec.get("harden_rc") not in (0, None) and t["done"]:
            state = "failed a check"
        print(f"{os.path.basename(d):16} " + " ".join(m(t[st]) for st, _ in STAGES[:4]) +
              f" {m(t['route']):>7} {m(t['signoff']):>7} {m(total):>7} "
              f"{(f'{wall:5.1f}m' if isinstance(wall, (int, float)) else '    -')}  {state}")


if __name__ == "__main__":
    main()
