"""Chip-level arithmetic model (team Spec 1-4): exactly what the silicon computes.

The multiplier uses K-RED reduction: each round multiplies by 13 mod q, so with R rounds it returns
FACTOR * a * b mod q, FACTOR = 13^R. Constants are stored scaled so the factor cancels in the NTT modes:
    ROM'[k]  = ZETAS[k] * FACTOR^-1
    gamma'_i = +-ROM'[64 + i//2]
    scale constant = 3303 * FACTOR^-2
Pins therefore show: forward/inverse NTT plain; basemul = FACTOR * plain; scale = c * 3303 * FACTOR^-1.

Which chip (environment variable NTT_CHIP, read once at import):
    team (default)  the tapeout chip, chipathon-2026 tt_um_NTT_Core: 3 rounds, FACTOR 2197, scale 304
    own             this repo's exploration RTL, src/ tt_um_ntt_engine: 2 rounds, FACTOR 169, scale 1441
"""
import os

from mlkem_ntt_model import Q, ZETAS

CHIP = os.environ.get("NTT_CHIP", "team").strip() or "team"
ROUNDS = {"team": 3, "own": 2}[CHIP]
FACTOR = 13 ** ROUNDS                  # carried by basemul results, removed by scale
INV_FACTOR = pow(FACTOR, -1, Q)        # 944 (team) or 2285 (own)
SCALE_CONST = 3303 * INV_FACTOR * INV_FACTOR % Q   # 304 (team) or 1441 (own)

ROM_P = [z * INV_FACTOR % Q for z in ZETAS]       # what zeta_rom.v stores


def kred(x):
    """One K-RED round: 13 * x[7:0] - (x >> 8), congruent to 13 * x."""
    return 13 * (x & 0xFF) - (x >> 8)


def mul(a, b):
    """modq_mul: ROUNDS K-RED rounds and a final correction -> FACTOR * a * b mod q."""
    assert 0 <= a < Q and 0 <= b < Q
    r = a * b
    for _ in range(ROUNDS):
        r = kred(r)
    return r % Q


mul169 = mul            # older name, kept for existing callers


def gamma_p(i):
    g = ROM_P[64 + (i >> 1)]
    return Q - g if i & 1 else g


def ct(a, b, idx):
    """Forward butterfly with ROM'[idx]: r0 = a + b*zeta, r1 = a - b*zeta."""
    t = mul(b, ROM_P[idx])
    return (a + t) % Q, (a - t) % Q


def gs(a, b, idx):
    """Inverse butterfly: r0 = a + b, r1 = (b - a) * zeta."""
    return (a + b) % Q, mul((b - a) % Q, ROM_P[idx])


def basemul_piece(f0, f1, g0, g1, i):
    """Five products in the chip's order; returns (c0, c1) = FACTOR * plain."""
    m1 = mul(f1, g1)
    m2 = mul(m1, gamma_p(i))
    m3 = mul(f0, g0)
    m4 = mul(f0, g1)
    m5 = mul(f1, g0)
    return (m2 + m3) % Q, (m4 + m5) % Q


def scale(c):
    return mul(c, SCALE_CONST)
