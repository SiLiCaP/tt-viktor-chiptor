"""ML-KEM (FIPS 203) in plain arithmetic, with the polynomial arithmetic behind a backend object.

Only NTT, inverse NTT, basemul and scale go through the backend: exactly the operations the
coprocessor offloads. Hashing, sampling, encoding, compression and the re-encrypt compare stay
here, on the "host".

    from mlkem import MLKEM512, MLKEM768
    kem = MLKEM768()                       # reference backend
    kem = MLKEM768(backend=my_chip)        # anything with ntt / invntt / basemul / scale
    ek, dk = kem.keygen_internal(d, z)
    K, c = kem.encaps_internal(ek, m)
    K2 = kem.decaps(dk, c)

Algorithm numbers in comments refer to FIPS 203 (Aug 2024).
"""
import hashlib
import os

from mlkem_ntt_model import N, Q, basemul_rom, intt_ref, ntt_ref

INV128 = 3303   # 128^-1 mod q


# ---------- backend interface ----------
class ReferenceBackend:
    """Golden-model backend. invntt is the 7 GS layers without the final x128^-1; scale does that."""

    def ntt(self, f):
        return ntt_ref(f)

    def invntt(self, f):
        return [x * 128 % Q for x in intt_ref(f)]     # undo intt_ref's built-in scale

    def basemul(self, f, g):
        return basemul_rom(f, g)

    def scale(self, f):
        return [x * INV128 % Q for x in f]


class CountingBackend:
    """Wraps a backend and counts calls per op (each call = one full 256-coefficient polynomial)."""

    def __init__(self, inner):
        self.inner = inner
        self.counts = {"ntt": 0, "invntt": 0, "basemul": 0, "scale": 0}

    def __getattr__(self, op):
        fn = getattr(self.inner, op)

        def counted(*args):
            self.counts[op] += 1
            return fn(*args)
        return counted


# ---------- hashing (section 4.1) ----------
def H(s):
    return hashlib.sha3_256(s).digest()


def J(s):
    return hashlib.shake_256(s).digest(32)


def G(s):
    h = hashlib.sha3_512(s).digest()
    return h[:32], h[32:]


def PRF(eta, s, b):
    return hashlib.shake_256(s + bytes([b])).digest(64 * eta)


# ---------- encoding and compression (4.2.1) ----------
def byte_encode(F, d):                                 # Algorithm 5
    m = (1 << d) if d < 12 else Q
    bits = 0
    for i, a in enumerate(F):
        assert 0 <= a < m
        bits |= a << (i * d)
    return bits.to_bytes(32 * d, "little")


def byte_decode(B, d):                                 # Algorithm 6
    m = (1 << d) if d < 12 else Q
    bits = int.from_bytes(B, "little")
    mask = (1 << d) - 1
    return [((bits >> (i * d)) & mask) % m for i in range(N)]


def compress(x, d):
    return ((x << d) + Q // 2) // Q % (1 << d)        # round(2^d / q * x) mod 2^d, exact integers


def decompress(y, d):
    return (y * Q + (1 << (d - 1))) >> d               # round(q / 2^d * y)


# ---------- sampling (4.2.2) ----------
def sample_ntt(B):                                     # Algorithm 7, B = rho || j || i
    xof = hashlib.shake_128(B)
    nbytes = 840                                       # enough >99.9999% of the time; extend if not
    buf = xof.digest(nbytes)
    a, pos = [], 0
    while len(a) < N:
        if pos + 3 > len(buf):
            nbytes *= 2
            buf = xof.digest(nbytes)
        c0, c1, c2 = buf[pos], buf[pos + 1], buf[pos + 2]
        pos += 3
        d1 = c0 + 256 * (c1 % 16)
        d2 = (c1 // 16) + 16 * c2
        if d1 < Q:
            a.append(d1)
        if d2 < Q and len(a) < N:
            a.append(d2)
    return a


def sample_poly_cbd(B, eta):                           # Algorithm 8
    bits = int.from_bytes(B, "little")
    f = []
    for i in range(N):
        x = sum((bits >> (2 * i * eta + j)) & 1 for j in range(eta))
        y = sum((bits >> (2 * i * eta + eta + j)) & 1 for j in range(eta))
        f.append((x - y) % Q)
    return f


def padd(f, g):
    return [(a + b) % Q for a, b in zip(f, g)]


def psub(f, g):
    return [(a - b) % Q for a, b in zip(f, g)]


# ---------- ML-KEM ----------
class MLKEM:
    def __init__(self, k, eta1, eta2, du, dv, backend=None):
        self.k, self.eta1, self.eta2, self.du, self.dv = k, eta1, eta2, du, dv
        self.be = backend or ReferenceBackend()

    # backend helpers: the only places polynomial arithmetic happens
    def _intt(self, f):
        return self.be.scale(self.be.invntt(f))

    def _dot(self, row, vec):
        """sum_j row[j] o vec[j] in the NTT domain (basemul on chip, additions on host)."""
        acc = [0] * N
        for a, b in zip(row, vec):
            acc = padd(acc, self.be.basemul(a, b))
        return acc

    def _matrix(self, rho, transpose=False):
        k = self.k
        A = [[sample_ntt(rho + bytes([j, i])) for j in range(k)] for i in range(k)]
        return [list(r) for r in zip(*A)] if transpose else A

    # K-PKE (section 5)
    def kpke_keygen(self, d):                          # Algorithm 13
        rho, sigma = G(d + bytes([self.k]))
        A = self._matrix(rho)
        nonce = 0
        s, e = [], []
        for _ in range(self.k):
            s.append(sample_poly_cbd(PRF(self.eta1, sigma, nonce), self.eta1)); nonce += 1
        for _ in range(self.k):
            e.append(sample_poly_cbd(PRF(self.eta1, sigma, nonce), self.eta1)); nonce += 1
        s_hat = [self.be.ntt(p) for p in s]
        e_hat = [self.be.ntt(p) for p in e]
        t_hat = [padd(self._dot(A[i], s_hat), e_hat[i]) for i in range(self.k)]
        ek = b"".join(byte_encode(t, 12) for t in t_hat) + rho
        dk = b"".join(byte_encode(s, 12) for s in s_hat)
        return ek, dk

    def kpke_encrypt(self, ek, m, r):                  # Algorithm 14
        k = self.k
        t_hat = [byte_decode(ek[384 * i:384 * (i + 1)], 12) for i in range(k)]
        rho = ek[384 * k:384 * k + 32]
        At = self._matrix(rho, transpose=True)
        nonce = 0
        y, e1 = [], []
        for _ in range(k):
            y.append(sample_poly_cbd(PRF(self.eta1, r, nonce), self.eta1)); nonce += 1
        for _ in range(k):
            e1.append(sample_poly_cbd(PRF(self.eta2, r, nonce), self.eta2)); nonce += 1
        e2 = sample_poly_cbd(PRF(self.eta2, r, nonce), self.eta2)
        y_hat = [self.be.ntt(p) for p in y]
        u = [padd(self._intt(self._dot(At[i], y_hat)), e1[i]) for i in range(k)]
        mu = [decompress(b, 1) for b in byte_decode(m, 1)]
        v = padd(padd(self._intt(self._dot(t_hat, y_hat)), e2), mu)
        c1 = b"".join(byte_encode([compress(x, self.du) for x in p], self.du) for p in u)
        c2 = byte_encode([compress(x, self.dv) for x in v], self.dv)
        return c1 + c2

    def kpke_decrypt(self, dk, c):                     # Algorithm 15
        k, du, dv = self.k, self.du, self.dv
        c1, c2 = c[:32 * du * k], c[32 * du * k:]
        u = [[decompress(x, du) for x in byte_decode(c1[32 * du * i:32 * du * (i + 1)], du)] for i in range(k)]
        v = [decompress(x, dv) for x in byte_decode(c2, dv)]
        s_hat = [byte_decode(dk[384 * i:384 * (i + 1)], 12) for i in range(k)]
        u_hat = [self.be.ntt(p) for p in u]
        w = psub(v, self._intt(self._dot(s_hat, u_hat)))
        return byte_encode([compress(x, 1) for x in w], 1)

    # ML-KEM internal (section 6)
    def keygen_internal(self, d, z):                   # Algorithm 16
        ek, dk_pke = self.kpke_keygen(d)
        return ek, dk_pke + ek + H(ek) + z

    def encaps_internal(self, ek, m):                  # Algorithm 17
        K, r = G(m + H(ek))
        return K, self.kpke_encrypt(ek, m, r)

    def decaps_internal(self, dk, c):                  # Algorithm 18
        k = self.k
        dk_pke = dk[:384 * k]
        ek = dk[384 * k:768 * k + 32]
        h = dk[768 * k + 32:768 * k + 64]
        z = dk[768 * k + 64:768 * k + 96]
        m2 = self.kpke_decrypt(dk_pke, c)
        K2, r2 = G(m2 + h)
        K_bar = J(z + c)
        c2 = self.kpke_encrypt(ek, m2, r2)
        return K2 if c == c2 else K_bar                # the host does this compare, not the chip

    # input checks (section 7)
    def ek_check(self, ek):
        k = self.k
        if len(ek) != 384 * k + 32:
            return False
        return all(byte_encode(byte_decode(ek[384 * i:384 * (i + 1)], 12), 12) == ek[384 * i:384 * (i + 1)]
                   for i in range(k))

    def dk_check(self, dk):
        k = self.k
        if len(dk) != 768 * k + 96:
            return False
        return H(dk[384 * k:768 * k + 32]) == dk[768 * k + 32:768 * k + 64]

    # public API with randomness (Algorithms 19-21)
    def keygen(self):
        return self.keygen_internal(os.urandom(32), os.urandom(32))

    def encaps(self, ek):
        if not self.ek_check(ek):
            raise ValueError("encapsulation key check failed")
        return self.encaps_internal(ek, os.urandom(32))

    def decaps(self, dk, c):
        if len(c) != 32 * (self.du * self.k + self.dv) or not self.dk_check(dk):
            raise ValueError("decapsulation input check failed")
        return self.decaps_internal(dk, c)


def MLKEM512(backend=None):
    return MLKEM(2, 3, 2, 10, 4, backend)


def MLKEM768(backend=None):
    return MLKEM(3, 2, 2, 10, 4, backend)


PARAMS = {"ML-KEM-512": MLKEM512, "ML-KEM-768": MLKEM768}
