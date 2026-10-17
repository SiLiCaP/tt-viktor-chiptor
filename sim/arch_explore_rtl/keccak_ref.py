"""Plain Keccak-f[1600] and a SHA3/SHAKE sponge, checked against hashlib. Reference for keccak_lane.v."""
import hashlib

RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
      0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
      0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
      0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
      0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
R = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]  # R[x][y]
M = (1 << 64) - 1


def rotl(v, n):
    return ((v << n) | (v >> (64 - n))) & M if n else v


def keccak_f(A):
    """A: list of 25 lanes, index x + 5y."""
    A = list(A)
    for rnd in range(24):
        C = [A[x] ^ A[x + 5] ^ A[x + 10] ^ A[x + 15] ^ A[x + 20] for x in range(5)]
        D = [C[(x - 1) % 5] ^ rotl(C[(x + 1) % 5], 1) for x in range(5)]
        B = [0] * 25
        for x in range(5):
            for y in range(5):
                B[y + 5 * ((2 * x + 3 * y) % 5)] = rotl(A[x + 5 * y] ^ D[x], R[x][y])
        A = [B[x + 5 * y] ^ (~B[(x + 1) % 5 + 5 * y] & B[(x + 2) % 5 + 5 * y]) & M for y in range(5) for x in range(5)]
        A = [A[i] if i else A[0] ^ RC[rnd] for i in range(25)]
    return A


def sponge(msg, rate, pad, outlen):
    S = [0] * 25
    m = bytearray(msg) + bytes([pad])
    while len(m) % rate:
        m.append(0)
    m[-1] |= 0x80
    for blk in range(0, len(m), rate):
        for i in range(rate // 8):
            S[i] ^= int.from_bytes(m[blk + 8 * i:blk + 8 * i + 8], "little")
        S = keccak_f(S)
    out = b""
    while len(out) < outlen:
        out += b"".join(S[i].to_bytes(8, "little") for i in range(rate // 8))
        if len(out) < outlen:
            S = keccak_f(S)
    return out[:outlen]


if __name__ == "__main__":
    for n in (0, 1, 135, 136, 300):
        msg = bytes(range(256))[:n] * 1
        assert sponge(msg, 136, 0x06, 32) == hashlib.sha3_256(msg).digest()
        assert sponge(msg, 168, 0x1F, 500) == hashlib.shake_128(msg).digest(500)
        assert sponge(msg, 136, 0x1F, 200) == hashlib.shake_256(msg).digest(200)
        assert sponge(msg, 72, 0x06, 64) == hashlib.sha3_512(msg).digest()
    print("keccak_ref: SHA3-256/512 and SHAKE128/256 match hashlib")
