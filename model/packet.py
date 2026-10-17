"""Send a packet with the ML-KEM shared key (a KEM-DEM construction, standard library only).

    blob = seal(K, b"hello")          # nonce (16) || ciphertext || tag (32)
    open_(K, blob) -> b"hello"        # raises ValueError if anything was changed

Keys: SHAKE256(K || label) -> 32-byte encryption key + 32-byte MAC key.
Encryption: XOR with SHAKE256(k_enc || nonce). Authentication: HMAC-SHA3-256 over nonce || ciphertext.
Demo construction: a product would use a standard AEAD such as AES-256-GCM with HKDF.
"""
import hashlib
import hmac
import os

LABEL = b"chipathon ML-KEM demo packet v1"


def _keys(K):
    k = hashlib.shake_256(K + LABEL).digest(64)
    return k[:32], k[32:]


def seal(K, msg, nonce=None):
    nonce = nonce or os.urandom(16)
    k_enc, k_mac = _keys(K)
    stream = hashlib.shake_256(k_enc + nonce).digest(len(msg))
    ct = bytes(a ^ b for a, b in zip(msg, stream))
    tag = hmac.new(k_mac, nonce + ct, hashlib.sha3_256).digest()
    return nonce + ct + tag


def open_(K, blob):
    nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
    k_enc, k_mac = _keys(K)
    if not hmac.compare_digest(tag, hmac.new(k_mac, nonce + ct, hashlib.sha3_256).digest()):
        raise ValueError("authentication failed: wrong key or tampered packet")
    stream = hashlib.shake_256(k_enc + nonce).digest(len(ct))
    return bytes(a ^ b for a, b in zip(ct, stream))
