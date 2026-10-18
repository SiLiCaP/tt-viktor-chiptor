"""Tile-size experiments for the team chip and its SHA-3 routes: build a variant, test it, harden it.

    python3 tools/tile_exp.py list                     # the experiment table below
    python3 tools/tile_exp.py run NAME [NAME ...]      # prepare, test and harden (each in its own folder)
    python3 tools/tile_exp.py status                   # where every run is, and its signoff numbers

A variant starts from a branch of chipathon-2026 (git archive of origin/<branch>, or of the local branch for
"local:<branch>", so no working tree is touched), then:
  top       "ntt+hash": the branch's own top (NTT core + Keccak core sharing the pins)
            "hash":     SHA-only: the NTT path removed, the hash words and their pin protocol unchanged
  core      keccak_ring K = 8 / 4 / 2 (branch sha3-4x2) or keccak_lat (branch sha3-latch)
            "own":      the branch's top as committed (only HASH_K and the tile size change)
  tiles     info.yaml tile size
  flow      "default": Tiny Tapeout's config as is
            "relaxed": the team's research settings (sha3-asic-research): hold uncertainty 0.14 ns SDC,
                       hold margins 0.03 / 0.02, small cells allowed, clkdlybuf delay cells banned, density 75
                       ("relaxed:d65": the same at placement density 65)
            "branch":  the branch's config.json as committed
            "latch":   small cells allowed, clkdlybuf banned, default hold (the keccak_lat recipe)
Results: ~/tools/work/exp/<name>/result.json and tools/tile_exp_results.json (summary).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEAM = os.path.join(os.path.dirname(ROOT), "chipathon-2026")
WORK = os.path.expanduser("~/tools/work/exp")
RESEARCH = os.path.expanduser("~/tools/work/br/sha3-asic-research/research/sha3")
SUMMARY = os.path.join(HERE, "tile_exp_results.json")
TT_TOOLS = os.path.expanduser("~/tools/tt-support-tools")
ENV_PATH = f"{os.path.expanduser('~/tools/bin')}:{os.path.expanduser('~/tools/tt-venv/bin')}:{os.environ['PATH']}"

# name: (branch, top, core, K, tiles, flow)
EXPERIMENTS = {
    # NTT alone (main)
    "ntt_1x2":         ("main", "ntt", None, None, "1x2", "default"),
    "ntt_2x2":         ("main", "ntt", None, None, "2x2", "default"),
    # SHA-only: the NTT core cut out
    "sha_k8_2x2":      ("sha3-4x2", "hash", "ring", 8, "2x2", "relaxed"),
    "sha_k4_2x2":      ("sha3-4x2", "hash", "ring", 4, "2x2", "relaxed"),
    "sha_k2_2x2":      ("sha3-4x2", "hash", "ring", 2, "2x2", "relaxed"),
    "sha_k8_2x2_def":  ("sha3-4x2", "hash", "ring", 8, "2x2", "default"),
    "sha_k4_2x2_d65":  ("sha3-4x2", "hash", "ring", 4, "2x2", "relaxed:d65"),
    "sha_k4_2x2_d70":  ("sha3-4x2", "hash", "ring", 4, "2x2", "relaxed:d70"),
    "sha_k8_3x2":      ("sha3-4x2", "hash", "ring", 8, "3x2", "relaxed"),
    "sha_k8_3x2_def":  ("sha3-4x2", "hash", "ring", 8, "3x2", "default"),
    "sha_lat_3x2":     ("sha3-latch", "hash", "lat", 8, "3x2", "latch"),
    # NTT + hash, the team's routes
    "both_k8_3x2":     ("sha3-4x2", "ntt+hash", "ring", 8, "3x2", "relaxed"),
    "both_k8_4x2":     ("sha3-4x2", "ntt+hash", "ring", 8, "4x2", "relaxed"),
    "both_lat_4x2":    ("sha3-latch", "ntt+hash", "lat", 8, "4x2", "latch"),
    # the hash-only chip (branch sha3-only: hash_io bursts + SamplePolyCBD, its own relaxed config)
    "hash_k8_2x2":     ("local:sha3-only", "own", "ring", 8, "2x2", "branch"),
    "hash_k8_3x2":     ("local:sha3-only", "own", "ring", 8, "3x2", "branch"),
    "hash_k16_3x2":    ("local:sha3-only", "own", "ring", 16, "3x2", "branch"),
    "hash_k16_2x2":    ("local:sha3-only", "own", "ring", 16, "2x2", "branch"),
}

SHA_TOP = """// SHA-only variant of the team chip (tools/tile_exp.py in tt-viktor-chiptor): the NTT core cut out, the
// pin protocol of the hash words unchanged (Spec 5 draft on sha3-4x2: valid = 1 and coeff[11:8] = 0xF;
// {sof, op} = command, coeff[K-1:0] = data; uo_out = the squeezed bits).
`default_nettype none

module tt_um_NTT_Core #(
    parameter HASH_K = 8
) (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
  wire [11:0] coeff_q;
  wire        valid_q, sof_q;
  wire [1:0]  op_q;
  io_in_capture u_in (.clk(clk), .rst_n(rst_n), .ui_in(ui_in), .uio_in(uio_in),
                      .coeff_q(coeff_q), .valid_q(valid_q), .sof_q(sof_q), .op_q(op_q));
  wire hash_in = uio_in[4] & (uio_in[3:0] == 4'hF);
  reg  hash_w;
  always @(posedge clk) begin
    if (!rst_n) hash_w <= 1'b0;
    else        hash_w <= hash_in;
  end
  wire [HASH_K-1:0] hash_dout;
  CORE #(.K(HASH_K)) u_hash (.clk(clk), .rst_n(rst_n), .cmd_valid(hash_w), .cmd({sof_q, op_q}),
                             .din(coeff_q[HASH_K-1:0]), .dout(hash_dout), .busy());
  assign uo_out  = {{(8 - HASH_K){1'b0}}, hash_dout};
  assign uio_out = 8'h00;
  assign uio_oe  = 8'h00;
  wire _unused = &{ena, valid_q, coeff_q[11:HASH_K], 1'b0};
endmodule
"""


def sh(cmd, cwd=None, log=None, env=None):
    with open(log, "a") if log else open(os.devnull, "w") as fh:
        return subprocess.run(cmd, cwd=cwd, shell=True, stdout=fh, stderr=subprocess.STDOUT, env=env).returncode


def prepare(name):
    branch, top, core, K, tiles, flow = EXPERIMENTS[name]
    flow, _, dens = flow.partition(":d")
    dens = int(dens) if dens else 75
    d = os.path.join(WORK, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    ref = branch[6:] if branch.startswith("local:") else f"origin/{branch}"
    subprocess.run(f"git -C {TEAM} archive {ref} | tar -x -C {d}", shell=True, check=True)
    src = os.path.join(d, "src")
    if core == "ring" and not os.path.exists(os.path.join(src, "keccak_ring.v")):
        shutil.copy(os.path.join(RESEARCH, "keccak_ring.v"), src)
    if top == "ntt+hash" and core == "ring":
        shutil.copy(os.path.join(RESEARCH, "top", "tt_um_NTT_Core.v"), src)   # registered hash decode
    core_file = {"ring": "keccak_ring.v", "lat": "keccak_lat.v", None: None}[core]
    y = open(os.path.join(d, "info.yaml")).read()
    y = re.sub(r'tiles: "\w+"', f'tiles: "{tiles}"', y)
    if top == "hash":
        with open(os.path.join(src, "tt_um_NTT_Core.v"), "w") as fh:
            fh.write(SHA_TOP.replace("CORE", {"ring": "keccak_ring", "lat": "keccak_lat"}[core]))
        files = ["tt_um_NTT_Core.v", "io_in_capture.v", core_file]
        y = re.sub(r"(  source_files:\n)(?:    - .*\n)+", lambda m: m.group(1) + "".join(f'    - "{f}"\n' for f in files), y)
    elif core_file and core_file not in y:
        y = y.replace('    - "modq_acc.v"\n', f'    - "modq_acc.v"\n    - "{core_file}"\n')
    with open(os.path.join(d, "info.yaml"), "w") as fh:
        fh.write(y)
    if K and top != "ntt":
        tp = os.path.join(src, "tt_um_NTT_Core.v")
        v = open(tp).read()
        open(tp, "w").write(re.sub(r"parameter HASH_K = \d+", f"parameter HASH_K = {K}", v))
    # flow settings
    c = open(os.path.join(src, "config.json")).read()
    extra = {"DRT_THREADS": "6"}      # the router's memory grows with its threads: 3 runs at once on 15 GB
    if flow in ("relaxed", "latch"):
        shutil.copy(os.path.join(RESEARCH, "no_synth_small.cells"), os.path.join(src, "no_synth.cells"))
        extra["SYNTH_EXCLUDED_CELL_FILE"] = '"dir::no_synth.cells"'
        extra["EXTRA_EXCLUDED_CELLS"] = '["sky130_fd_sc_hd__clkdlybuf4s*"]'
    if flow == "relaxed":
        shutil.copy(os.path.join(RESEARCH, "hold14.sdc"), os.path.join(src, "custom.sdc"))
        extra["PNR_SDC_FILE"] = '"dir::custom.sdc"'
        extra["SIGNOFF_SDC_FILE"] = '"dir::custom.sdc"'
        c = re.sub(r'"PL_RESIZER_HOLD_SLACK_MARGIN": [\d.]+', '"PL_RESIZER_HOLD_SLACK_MARGIN": 0.03', c)
        c = re.sub(r'"GRT_RESIZER_HOLD_SLACK_MARGIN": [\d.]+', '"GRT_RESIZER_HOLD_SLACK_MARGIN": 0.02', c)
        c = re.sub(r'"PL_TARGET_DENSITY_PCT": \d+', f'"PL_TARGET_DENSITY_PCT": {dens}', c)
    for k, val in extra.items():
        c = c.replace('  "CLOCK_PORT": "clk",', f'  "CLOCK_PORT": "clk",\n  "{k}": {val},')
    open(os.path.join(src, "config.json"), "w").write(c)
    # tests: the SHA-only top has no NTT, so only the hash algorithm tests apply
    mk = os.path.join(d, "test", "Makefile")
    m = open(mk).read()
    srcs = re.search(r"PROJECT_SOURCES = ((?:.*\\\n)*.*)\n", m)
    if top == "own":
        pass
    elif top == "hash":
        m = m.replace(srcs.group(0), f"PROJECT_SOURCES = tt_um_NTT_Core.v io_in_capture.v {core_file}\n")
        m = re.sub(r"COCOTB_TEST_MODULES = .*", "COCOTB_TEST_MODULES = test_hash\nexport COCOTB_TEST_FILTER = test_hash_algos", m)
    elif core_file and core_file not in srcs.group(0):
        m = m.replace(srcs.group(0), srcs.group(0) + f" {core_file}")
    open(mk, "w").write(m)
    subprocess.run(f"cd {d} && git init -q && git add -A && git -c user.email=x@y -c user.name=exp commit -qm '{name}' "
                   f"&& ln -sfn {TT_TOOLS} tt", shell=True, check=True)
    return d


def test(name, d, log):
    branch, top, _, K, _, _ = EXPERIMENTS[name]
    if top == "ntt" and branch == "main":
        return None                                     # main is tested by its own CI
    env = dict(os.environ, PATH=f"{os.path.expanduser('~/tools/oss-cad-suite/bin')}:{os.environ['PATH']}")
    if top == "own":
        env["HASH_K"] = str(K)
    rc = sh("source ~/tools/oss-cad-suite/environment && cd test && make -s 2>&1", cwd=d, log=log, env=env)
    res = os.path.join(d, "test", "results.xml")
    if not os.path.exists(res):
        return {"ran": False, "rc": rc}
    import xml.etree.ElementTree as ET
    cases = list(ET.parse(res).getroot().iter("testcase"))
    fail = [tc.get("name") for tc in cases if tc.find("failure") is not None or tc.find("error") is not None]
    return {"ran": True, "tests": len(cases), "failed": fail}


def harden(d, log):
    env = dict(os.environ, PATH=ENV_PATH)
    sh("python ./tt/tt_tool.py --create-user-config", cwd=d, log=log, env=env)
    t = time.time()
    rc = sh("python ./tt/tt_tool.py --harden", cwd=d, log=log, env=env)
    return rc, time.time() - t


def metrics(d):
    runs = os.path.join(d, "runs", "wokwi")
    out = {}
    syn = os.path.join(runs, "06-yosys-synthesis", "state_out.json")
    if os.path.exists(syn):
        m = json.load(open(syn)).get("metrics", {})
        out["synth_area"] = m.get("design__instance__area")
        out["synth_cells"] = m.get("design__instance__count")
    fin = os.path.join(runs, "final", "metrics.json")
    if os.path.exists(fin):
        m = json.load(open(fin))
        for k in ("design__instance__area__stdcell", "design__instance__utilization", "route__drc_errors",
                  "magic__drc_error__count", "antenna__violating__nets", "design__lvs_error__count",
                  "timing__setup__ws__corner:max_ss_100C_1v60", "timing__setup__ws__corner:nom_tt_025C_1v80",
                  "timing__hold__ws", "timing__setup_vio__count", "timing__hold_vio__count",
                  "design__max_slew_violation__count__corner:max_ss_100C_1v60"):
            out[k] = m.get(k)
    steps = sorted((s for s in os.listdir(runs) if re.match(r"\d+-", s)), key=lambda s: int(s.split("-")[0])) \
        if os.path.isdir(runs) else []
    out["last_step"] = steps[-1] if steps else None
    hb = subprocess.run(f"grep -h 'Inserted .* hold buffers' {runs}/*/*.log 2>/dev/null | tail -1", shell=True,
                        capture_output=True, text=True).stdout.strip()
    if hb:
        out["hold_buffers"] = hb
    err = subprocess.run(f"grep -h -m1 -E '\\[ERROR|ERROR ' {runs}/*/*.log 2>/dev/null | tail -1", shell=True,
                         capture_output=True, text=True).stdout.strip()
    if err:
        out["first_error"] = err[:300]
    return out


def save(name, rec):
    with open(os.path.join(WORK, name, "result.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    allr = json.load(open(SUMMARY)) if os.path.exists(SUMMARY) else {}
    allr[name] = rec
    with open(SUMMARY, "w") as fh:
        json.dump(allr, fh, indent=1, sort_keys=True)


def run(name):
    d = prepare(name)
    log = os.path.join(d, "exp.log")
    rec = {"experiment": dict(zip(("branch", "top", "core", "K", "tiles", "flow"), EXPERIMENTS[name])),
           "started": time.strftime("%Y-%m-%d %H:%M")}
    rec["tests"] = test(name, d, log)
    save(name, rec)
    rc, secs = harden(d, log)
    rec.update({"harden_rc": rc, "harden_min": round(secs / 60, 1), "metrics": metrics(d)})
    rec["fits"] = rc == 0 and rec["metrics"].get("design__instance__utilization") is not None
    save(name, rec)
    print(f"{name}: harden rc {rc} in {secs / 60:.0f} min, {rec['metrics']}")


def status():
    for name in EXPERIMENTS:
        d = os.path.join(WORK, name)
        if not os.path.isdir(d):
            print(f"{name:16} not started")
            continue
        m = metrics(d)
        r = json.load(open(os.path.join(d, "result.json"))) if os.path.exists(os.path.join(d, "result.json")) else {}
        state = "done" if "harden_rc" in r else "running"
        t = r.get("tests")
        ts = f"tests {t['tests'] - len(t['failed'])}/{t['tests']}" if t and t.get("ran") else ("tests -" if t is None else "tests ERR")
        print(f"{name:16} {state:8} {ts:12} {m.get('last_step')}  util {m.get('design__instance__utilization')}  "
              f"ss {m.get('timing__setup__ws__corner:max_ss_100C_1v60')}  {m.get('hold_buffers', '')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for k, v in EXPERIMENTS.items():
            print(f"{k:16} {v}")
    elif cmd == "run":
        for n in sys.argv[2:]:
            run(n)
    elif cmd == "status":
        status()
