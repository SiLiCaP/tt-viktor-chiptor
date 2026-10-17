"""Pin protocol constants for the NTT coprocessor (docs/PROTOCOL.md). Single source of truth:
the chip models, the host model, the report and (later) the RTL tests all read these.

STATUS: APPROVED 2026-10-17. Change them here only, and only with team agreement.

Cycle convention (same as cocotb and the Tang Nano rig): in cycle t the host drives the inputs,
samples uo_out, then the rising edge happens. All outputs are registered, so uo_out in cycle t only
depends on inputs from cycles < t.
"""

OP_CT, OP_GS, OP_BASEMUL, OP_SCALE = 0, 1, 2, 3
OP_NAMES = {OP_CT: "CT", OP_GS: "GS", OP_BASEMUL: "basemul", OP_SCALE: "scale"}

WORDS = {OP_CT: 2, OP_GS: 2, OP_SCALE: 2, OP_BASEMUL: 4}      # input words per transaction

# Stream transactions (design A, and design B's stream mode):
# PERIOD = minimum clocks between the first words of consecutive transactions
# LAT    = first result byte appears LAT clocks after the transaction's first word
PERIOD = {
    "serial":   {OP_CT: 3, OP_GS: 3, OP_SCALE: 6, OP_BASEMUL: 15},
    "parallel": {OP_CT: 3, OP_GS: 3, OP_SCALE: 3, OP_BASEMUL: 5},
}
LAT = {
    "serial":   {OP_CT: 8, OP_GS: 8, OP_SCALE: 10, OP_BASEMUL: 22},
    "parallel": {OP_CT: 6, OP_GS: 6, OP_SCALE: 6, OP_BASEMUL: 12},
}

# Design B block mode: header at cycle h, 16 data words at h+1 .. h+16 (consecutive),
# compute for C clocks, 24 result bytes at h+17+C .. h+17+C+23. Next header >= h+17+C+24.
BLOCK_WORDS = 16
BLOCK_BYTES = 24


def block_butterflies(pass_id):
    return 32 if pass_id in (0, 3) else 24          # 4 or 3 local layers x 8 butterflies


def block_compute(pass_id, mult):
    nbf = block_butterflies(pass_id)
    return 3 * nbf + 3 if mult == "serial" else nbf + 3


def block_lat(pass_id, mult):
    """Header cycle -> first result byte."""
    return 1 + BLOCK_WORDS + block_compute(pass_id, mult)


def block_period(pass_id, mult):
    return block_lat(pass_id, mult) + BLOCK_BYTES


# Header word (valid=1, sof=1) fields, design B only
def header(block_mode, pass_id=0, blk=0, shuffle=False):
    return (pass_id & 3) | (int(block_mode) << 2) | ((blk & 15) << 3) | (int(shuffle) << 7)


def parse_header(din):
    return {"pass_id": din & 3, "block_mode": bool(din >> 2 & 1), "blk": din >> 3 & 15,
            "shuffle": bool(din >> 7 & 1), "reserved": din >> 8}


# ByteEncode12 for one pair: b0 = v0[7:0], b1 = {v1[3:0], v0[11:8]}, b2 = v1[11:4]
def pack_pair(v0, v1):
    return [v0 & 0xFF, ((v1 & 0xF) << 4) | (v0 >> 8), v1 >> 4]


def unpack_pair(b0, b1, b2):
    return b0 | ((b1 & 0xF) << 8), (b1 >> 4) | (b2 << 4)
