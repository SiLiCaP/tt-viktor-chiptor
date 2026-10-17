"""
ML-KEM (FIPS 203) NTT golden model + streaming "2-pass, 16-coefficient block" schedule.

Purpose: reference for the Tiny Tapeout NTT coprocessor idea.
  - ntt_ref / intt_ref / basemul_ref follow FIPS 203 Algorithms 9, 10, 11, 12.
  - ntt_blocked shows the chip-side schedule: the host streams 16 coefficients
    at a time, the chip runs several NTT layers on them locally, streams 16 back.
    Pass 1: groups {r, r+16, ..., r+240}  -> layers len=128,64,32,16
    Pass 2: blocks {16b .. 16b+15}         -> layers len=8,4,2
  - barrett() is the hardware-friendly reduction mod q for 24-bit products.
Run:  python3 mlkem_ntt_model.py
"""
import random

Q = 3329
ZETA = 17          # primitive 256th root of unity mod Q
N = 256


def bitrev7(i):
    return int(f"{i:07b}"[::-1], 2)


ZETAS = [pow(ZETA, bitrev7(i), Q) for i in range(128)]   # the on-chip twiddle ROM (128 x 12 bit)


# ---------- modular arithmetic as hardware would do it ----------
BARRETT_M = (1 << 24) // Q     # 5039


def barrett(x):
    """Reduce 0 <= x < 2^24 (covers any 12x12-bit product) to [0, Q)."""
    assert 0 <= x < (1 << 24)
    t = (x * BARRETT_M) >> 24
    r = x - t * Q
    # one or two conditional subtractions
    if r >= Q:
        r -= Q
    if r >= Q:
        r -= Q
    return r


def modmul(a, b):
    return barrett(a * b)


def ct_butterfly(a, b, z):
    """Forward (Cooley-Tukey): a' = a + z*b, b' = a - z*b  (mod Q)."""
    t = modmul(z, b)
    return (a + t) % Q, (a - t) % Q


def gs_butterfly(a, b, z):
    """Inverse (Gentleman-Sande): a' = a + b, b' = z*(b - a)  (mod Q)."""
    return (a + b) % Q, modmul(z, (b - a) % Q)


# ---------- FIPS 203 reference ----------
def ntt_ref(f):
    f = list(f)
    i = 1
    length = 128
    while length >= 2:
        for start in range(0, N, 2 * length):
            z = ZETAS[i]; i += 1
            for j in range(start, start + length):
                t = z * f[j + length] % Q
                f[j + length] = (f[j] - t) % Q
                f[j] = (f[j] + t) % Q
        length //= 2
    return f


def intt_ref(f):
    f = list(f)
    i = 127
    length = 2
    while length <= 128:
        for start in range(0, N, 2 * length):
            z = ZETAS[i]; i -= 1
            for j in range(start, start + length):
                t = f[j]
                f[j] = (t + f[j + length]) % Q
                f[j + length] = z * (f[j + length] - t) % Q
        length *= 2
    return [x * 3303 % Q for x in f]      # 3303 = 128^-1 mod Q


def basemul_ref(fh, gh):
    """Multiply in NTT domain: 128 degree-1 products mod (X^2 - gamma)."""
    h = [0] * N
    for i in range(64):
        for k, sign in ((4 * i, 1), (4 * i + 2, -1)):
            gamma = sign * pow(ZETA, 2 * bitrev7(2 * i) + 1, Q) % Q  # = zeta^(2*BitRev7(i')+1)
            a0, a1, b0, b1 = fh[k], fh[k + 1], gh[k], gh[k + 1]
            h[k] = (a0 * b0 + a1 * b1 % Q * gamma) % Q
            h[k + 1] = (a0 * b1 + a1 * b0) % Q
    return h


def polymul_schoolbook(a, b):
    """Plain multiplication mod (X^256 + 1, Q) - the slow way, for checking."""
    c = [0] * N
    for i in range(N):
        for j in range(N):
            k = i + j
            if k < N:
                c[k] = (c[k] + a[i] * b[j]) % Q
            else:
                c[k - N] = (c[k - N] - a[i] * b[j]) % Q
    return c


# ---------- chip-side streaming schedule ----------
def ntt_blocked(f):
    """Two passes over the polynomial, 16 coefficients on-chip at a time."""
    f = list(f)
    total_bf = 0
    io_words = 0

    # Pass 1: residue groups mod 16, layers len = 128, 64, 32, 16
    for r in range(16):
        idx = [r + 16 * m for m in range(16)]     # global indices in this group
        buf = [f[g] for g in idx]                 # host -> chip
        io_words += 16
        for length in (128, 64, 32, 16):
            stride = length // 16                 # partner distance in local buffer
            for loc in range(16):
                g = idx[loc]
                if (g // length) % 2 == 0:        # g is the "top" element of its pair
                    start = g - g % (2 * length)
                    z = ZETAS[(N // (2 * length)) + start // (2 * length)]
                    a, b = buf[loc], buf[loc + stride]
                    buf[loc], buf[loc + stride] = ct_butterfly(a, b, z)
                    total_bf += 1
        for loc, g in enumerate(idx):             # chip -> host
            f[g] = buf[loc]
        io_words += 16

    # Pass 2: contiguous blocks of 16, layers len = 8, 4, 2
    for blk in range(16):
        base = 16 * blk
        buf = f[base:base + 16]
        io_words += 16
        for length in (8, 4, 2):
            for loc in range(16):
                g = base + loc
                if (g // length) % 2 == 0:
                    start = g - g % (2 * length)
                    z = ZETAS[(N // (2 * length)) + start // (2 * length)]
                    buf[loc], buf[loc + length] = ct_butterfly(buf[loc], buf[loc + length], z)
                    total_bf += 1
        f[base:base + 16] = buf
        io_words += 16

    return f, total_bf, io_words



# ---------- hardware-facing helpers (closed forms the RTL implements) ----------
def zidx_fwd(g, L):
    """Forward (CT) twiddle ROM index for the pair whose top element is global index g, distance L."""
    return N // (2 * L) + (g - g % (2 * L)) // (2 * L)


def zidx_inv(g, L):
    """Inverse (GS) twiddle ROM index for the pair whose top element is global index g, distance L."""
    return N // L - 1 - (g - g % (2 * L)) // (2 * L)


def basemul_gamma(i):
    """gamma for base-multiplication pair i (0..127): (-1)^(i&1) * ZETAS[64 + i//2]  (one ROM, no extra table)."""
    z = ZETAS[64 + (i >> 1)]
    return (Q - z) % Q if (i & 1) else z


def basemul_rom(fh, gh):
    """Same as basemul_ref but with gamma taken from the twiddle ROM as the chip does."""
    h = [0] * N
    for i in range(128):
        a0, a1, b0, b1 = fh[2 * i], fh[2 * i + 1], gh[2 * i], gh[2 * i + 1]
        g = basemul_gamma(i)
        h[2 * i] = (a0 * b0 + (a1 * b1 % Q) * g) % Q
        h[2 * i + 1] = (a0 * b1 + a1 * b0) % Q
    return h


# Block-engine (design B) local closed forms. ll = layer inside the pass, i = local index 0..15,
# blk = block number (r for strided passes, b for contiguous passes).
def b_stride_log2(pass_id, ll):
    return {0: 3 - ll, 1: 3 - ll, 2: ll + 1, 3: ll}[pass_id]


def b_zidx(pass_id, blk, ll, i):
    if pass_id == 0:   # forward, strided group r, L = 128 >> ll
        return (1 << ll) + (i >> (4 - ll))
    if pass_id == 1:   # forward, contiguous block b, L = 8 >> ll
        return (16 << ll) + (((blk << 4) | i) >> (4 - ll))
    if pass_id == 2:   # inverse, contiguous block b, L = 2 << ll
        return (127 >> ll) - (((blk << 4) | i) >> (ll + 2))
    return (15 >> ll) - (i >> (ll + 1))   # inverse, strided group r, L = 16 << ll


def b_pair(pass_id, ll, k):
    """k-th butterfly (0..7) of local layer ll -> local indices (i, j)."""
    s = b_stride_log2(pass_id, ll)
    i = ((k >> s) << (s + 1)) | (k & ((1 << s) - 1))
    return i, i + (1 << s)


def b_run_block(buf, pass_id, blk, order=None):
    """What the chip does to one 16-coefficient block. order(ll) -> permutation of 0..7 (shuffling)."""
    buf = list(buf)
    nl = 4 if pass_id in (0, 3) else 3
    for ll in range(nl):
        ks = order(ll) if order else range(8)
        for k in ks:
            i, j = b_pair(pass_id, ll, k)
            z = ZETAS[b_zidx(pass_id, blk, ll, i)]
            if pass_id < 2:
                buf[i], buf[j] = ct_butterfly(buf[i], buf[j], z)
            else:
                buf[i], buf[j] = gs_butterfly(buf[i], buf[j], z)
    return buf


def ntt_chip_b(f, order=None):
    f = list(f)
    for r in range(16):                      # pass 0: strided
        idx = [r + 16 * m for m in range(16)]
        out = b_run_block([f[g] for g in idx], 0, r, order)
        for loc, g in enumerate(idx): f[g] = out[loc]
    for b in range(16):                      # pass 1: contiguous
        f[16 * b:16 * b + 16] = b_run_block(f[16 * b:16 * b + 16], 1, b, order)
    return f


def intt_chip_b(f, order=None):
    f = list(f)
    for b in range(16):                      # pass 2: contiguous
        f[16 * b:16 * b + 16] = b_run_block(f[16 * b:16 * b + 16], 2, b, order)
    for r in range(16):                      # pass 3: strided
        idx = [r + 16 * m for m in range(16)]
        out = b_run_block([f[g] for g in idx], 3, r, order)
        for loc, g in enumerate(idx): f[g] = out[loc]
    return [x * 3303 % Q for x in f]         # 'scale' op


def ntt_even_odd(f):
    """Fact: the NTT is two independent 128-point NTTs on even and odd indices (same twiddles)."""
    out = list(f)
    for p in (0, 1):
        for L in (128, 64, 32, 16, 8, 4, 2):
            for g in range(p, N, 2):
                if (g // L) % 2 == 0:
                    out[g], out[g + L] = ct_butterfly(out[g], out[g + L], ZETAS[zidx_fwd(g, L)])
    return out


# Design A (butterfly stream): the host sends butterflies in canonical FIPS 203 order and the chip
# derives the twiddle from two counters (layer 0..6, butterfly n 0..127 within the layer).
def a_zidx_fwd(layer, n):
    return (1 << layer) + (n >> (7 - layer))


def a_zidx_inv(layer, n):
    return (127 >> layer) - (n >> (layer + 1))


def ntt_chip_a(f):
    f = list(f)
    for layer in range(7):
        L = 128 >> layer
        n = 0
        for start in range(0, N, 2 * L):
            for j in range(start, start + L):
                f[j], f[j + L] = ct_butterfly(f[j], f[j + L], ZETAS[a_zidx_fwd(layer, n)]); n += 1
    return f


def intt_chip_a(f):
    f = list(f)
    for layer in range(7):
        L = 2 << layer
        n = 0
        for start in range(0, N, 2 * L):
            for j in range(start, start + L):
                f[j], f[j + L] = gs_butterfly(f[j], f[j + L], ZETAS[a_zidx_inv(layer, n)]); n += 1
    return [x * 3303 % Q for x in f]

if __name__ == "__main__":
    rng = random.Random(1)

    # 1) Barrett reduction is exact for every possible 12x12 product input range
    for x in range(0, Q * Q):
        assert barrett(x) == x % Q
    print(f"barrett: exact for all x < q^2 (m = {BARRETT_M}, shift 24)")

    # 2) blocked 2-pass schedule == FIPS 203 NTT
    for _ in range(200):
        a = [rng.randrange(Q) for _ in range(N)]
        out, bf, io = ntt_blocked(a)
        assert out == ntt_ref(a)
    print(f"2-pass blocked NTT == FIPS 203 NTT  ({bf} butterflies, {io} coefficients moved, {io*12//8} bytes)")

    # 3) NTT round trip and fast multiply == schoolbook multiply
    a = [rng.randrange(Q) for _ in range(N)]
    b = [rng.randrange(Q) for _ in range(N)]
    assert intt_ref(ntt_ref(a)) == a
    assert intt_ref(basemul_ref(ntt_ref(a), ntt_ref(b))) == polymul_schoolbook(a, b)
    print("INTT(NTT(a)) == a, and INTT(basemul(NTT a, NTT b)) == a*b  -> model correct")


    # 4) hardware closed forms
    for _ in range(50):
        a = [rng.randrange(Q) for _ in range(N)]
        b = [rng.randrange(Q) for _ in range(N)]
        assert basemul_rom(a, b) == basemul_ref(a, b)
        assert ntt_chip_b(a) == ntt_ref(a)
        assert intt_chip_b(a) == intt_ref(a)
        assert ntt_even_odd(a) == ntt_ref(a)
        assert ntt_chip_a(a) == ntt_ref(a) and intt_chip_a(a) == intt_ref(a)
        perm = lambda ll: rng.sample(range(8), 8)       # random shuffle per layer
        assert ntt_chip_b(a, perm) == ntt_ref(a)
        assert intt_chip_b(a, perm) == intt_ref(a)
    print("design-A counter formulas and design-B closed forms (pairs, twiddle index, fwd+inv, shuffled order) == FIPS 203")
    print("basemul gamma = (-1)^(i&1) * ZETAS[64 + i//2]  == FIPS 203;  NTT = even/odd 128-point halves")
    print(f"twiddle ROM: {len(ZETAS)} entries x 12 bit, first 8: {ZETAS[:8]}")
