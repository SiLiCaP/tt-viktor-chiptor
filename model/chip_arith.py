"""Chip-level arithmetic model (team Spec 1-4): exactly what the silicon computes.

The multiplier uses K-RED reduction and returns 169 * a * b mod q. Constants are stored scaled so the
factor cancels in the NTT modes:
    ROM'[k]  = ZETAS[k] * 169^-1          (169^-1 = 2285)
    gamma'_i = +-ROM'[64 + i//2]
    scale constant 1441 = 3303 * 169^-2
Pins therefore show: forward/inverse NTT plain; basemul = 169 * plain; scale = c * 3303 * 169^-1.
"""
from mlkem_ntt_model import Q, ZETAS

INV169 = 2285
SCALE_CONST = 1441
FACTOR = 169                     # carried by basemul results, removed by scale

ROM_P = [z * INV169 % Q for z in ZETAS]          # what zeta_rom.v stores


def kred(x):
    """One K-RED round: 13 * x[7:0] - (x >> 8), congruent to 13 * x."""
    return 13 * (x & 0xFF) - (x >> 8)


def mul169(a, b):
    """modq_mul: two K-RED rounds and one correction -> 169 * a * b mod q (exhaustively checked)."""
    assert 0 <= a < Q and 0 <= b < Q
    r = kred(kred(a * b))
    if r < 0:
        r += Q
    elif r >= Q:
        r -= Q
    return r


def gamma_p(i):
    g = ROM_P[64 + (i >> 1)]
    return Q - g if i & 1 else g


def ct(a, b, idx):
    """Forward butterfly with ROM'[idx]: r0 = a + b*zeta, r1 = a - b*zeta."""
    t = mul169(b, ROM_P[idx])
    return (a + t) % Q, (a - t) % Q


def gs(a, b, idx):
    """Inverse butterfly: r0 = a + b, r1 = (b - a) * zeta."""
    return (a + b) % Q, mul169((b - a) % Q, ROM_P[idx])


def basemul_piece(f0, f1, g0, g1, i):
    """Five products in the chip's order; returns (c0, c1) = 169 * plain."""
    m1 = mul169(f1, g1)
    m2 = mul169(m1, gamma_p(i))
    m3 = mul169(f0, g0)
    m4 = mul169(f0, g1)
    m5 = mul169(f1, g0)
    return (m2 + m3) % Q, (m4 + m5) % Q


def scale(c):
    return mul169(c, SCALE_CONST)
