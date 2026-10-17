"""Pin protocol constants for the NTT coprocessor (docs/PROTOCOL.md, team Spec 1/3/5). Single source of
truth for the chip models, the host model, the report, the vector export and the RTL tests
(this is the spec's timing.py).

Cycle convention (same as cocotb and the Tang Nano rig): in cycle t the host drives the inputs,
samples uo_out, then the rising edge happens. All outputs are registered.

Output delays D follow from the RTL pipeline (Spec 3 "Latency and alignment"):
    input capture 1 + multiplier L_MULT 4 + adders 0 (combinational) + control + packer 1.
"""

OP_CT, OP_GS, OP_BASEMUL, OP_SCALE = 0, 1, 2, 3
OP_NAMES = {OP_CT: "forward", OP_GS: "inverse", OP_BASEMUL: "basemul", OP_SCALE: "scale"}

L_MULT = 4                                    # modq_mul start -> p_valid

# One "unit" = the inputs that produce one result pair.
#   forward/inverse: b = f[j+len], a = f[j]  -> (a', b')
#   basemul piece i: g1, f1, g0, f0          -> (c0, c1)
#   scale:           c0, c1 (3 clocks apart)  -> (c0', c1')
OFFSETS = {OP_CT: (0, 1), OP_GS: (0, 1), OP_BASEMUL: (0, 1, 2, 3), OP_SCALE: (0, 3)}
PERIOD = {OP_CT: 3, OP_GS: 3, OP_BASEMUL: 15, OP_SCALE: 6}     # unit start -> earliest next unit start
LAT = {OP_CT: 6, OP_GS: 7, OP_BASEMUL: 20, OP_SCALE: 9}        # D: unit's first input -> first result byte
JOB_INPUTS = {OP_CT: 1792, OP_GS: 1792, OP_BASEMUL: 512, OP_SCALE: 256}

# Proposed: Control uses the full-rate multiplier (team Spec 2, L_MUL = 3, one start per clock).
# NTT/INTT stay at 3 clocks per butterfly (3 result bytes on 8 pins); basemul becomes multiplier-bound
# (5 products per piece), scale becomes pin-bound (3 bytes per pair). docs/spec-changes/01_full_rate_multiplier.md
FULL_RATE = {
    "OFFSETS": {OP_CT: (0, 1), OP_GS: (0, 1), OP_BASEMUL: (0, 1, 2, 3), OP_SCALE: (0, 1)},
    "PERIOD": {OP_CT: 3, OP_GS: 3, OP_BASEMUL: 5, OP_SCALE: 3},
    "LAT": {OP_CT: 6, OP_GS: 7, OP_BASEMUL: 12, OP_SCALE: 7},
}


def use_full_rate():
    """Switch every importer of OFFSETS / PERIOD / LAT to the proposed full-rate schedule (in place)."""
    for name, table in FULL_RATE.items():
        globals()[name].update(table)


def _team_timing():
    """The team chip's timing, read from chipathon-2026/test/timing.py (the team's single source, also the
    source of the RP2350 firmware's timing.h) when that repo is next to this one; else the copy below,
    taken from it on Oct 17 (main acff283: full-rate basemul and scale, PRE_LAT = 1)."""
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "chipathon-2026", "test", "timing.py")
    if os.path.exists(path):
        spec = importlib.util.spec_from_file_location("team_timing", path)
        T = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(T)
        return ({OP_CT: tuple(T.OFFS_F), OP_GS: tuple(T.OFFS_I), OP_BASEMUL: tuple(T.OFFS_B), OP_SCALE: tuple(T.OFFS_S)},
                {OP_CT: T.P_F, OP_GS: T.P_I, OP_BASEMUL: T.P_B, OP_SCALE: T.P_S},
                {OP_CT: T.D_F, OP_GS: T.D_I, OP_BASEMUL: T.D_B, OP_SCALE: T.D_S}, path)
    return ({OP_CT: (0, 1), OP_GS: (0, 1), OP_BASEMUL: (0, 1, 2, 3), OP_SCALE: (0, 1)},
            {OP_CT: 3, OP_GS: 3, OP_BASEMUL: 5, OP_SCALE: 3},
            {OP_CT: 6, OP_GS: 8, OP_BASEMUL: 12, OP_SCALE: 7}, "built-in copy (acff283)")


# Which chip's timing (the same switch as model/chip_arith.py): team = tt_um_NTT_Core (default), own = src/.
import os as _os  # noqa: E402
CHIP = _os.environ.get("NTT_CHIP", "team").strip() or "team"
TIMING_SOURCE = "this file (own chip)"
if CHIP == "team":
    _o, _p, _l, TIMING_SOURCE = _team_timing()
    OFFSETS.update(_o)
    PERIOD.update(_p)
    LAT.update(_l)
JOB_UNITS = {op: JOB_INPUTS[op] // len(OFFSETS[op]) for op in OFFSETS}


def job_clocks(op):
    """Chip clocks of one call as the harness runs it: NTT jobs layer by layer (each layer's results come
    back before the next layer goes in), basemul and scale as one stream. Equals docs/host_timing.md."""
    per = {OP_CT: 7, OP_GS: 7}.get(op, 1)
    units = JOB_UNITS[op] // per
    return per * (units * PERIOD[op] + LAT[op] + 3)


# Design B (experimental, not in the team plan): block mode header and timing, serial multiplier.
BLOCK_WORDS = 16
BLOCK_BYTES = 24


def block_butterflies(pass_id):
    return 32 if pass_id in (0, 3) else 24


def block_compute(pass_id):
    return 3 * block_butterflies(pass_id) + 3


def block_lat(pass_id):
    return 1 + BLOCK_WORDS + block_compute(pass_id)


def block_period(pass_id):
    return block_lat(pass_id) + BLOCK_BYTES


def header(block_mode, pass_id=0, blk=0, shuffle=False):
    return (pass_id & 3) | (int(block_mode) << 2) | ((blk & 15) << 3) | (int(shuffle) << 7)


def parse_header(din):
    return {"pass_id": din & 3, "block_mode": bool(din >> 2 & 1), "blk": din >> 3 & 15,
            "shuffle": bool(din >> 7 & 1), "reserved": din >> 8}


# ByteEncode12 for one pair: b0 = r0[7:0], b1 = {r1[3:0], r0[11:8]}, b2 = r1[11:4]
def pack_pair(v0, v1):
    return [v0 & 0xFF, ((v1 & 0xF) << 4) | (v0 >> 8), v1 >> 4]


def unpack_pair(b0, b1, b2):
    return b0 | ((b1 & 0xF) << 8), (b1 >> 4) | (b2 << 4)
