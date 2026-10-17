"""model/mlkem.py against NIST ACVP vectors and kyber-py."""
import json
import os
import random

import pytest
from conftest import VECTORS

from mlkem import PARAMS, CountingBackend, ReferenceBackend

PARAMSETS = ("ML-KEM-512", "ML-KEM-768")


def groups(fname, function=None):
    j = json.load(open(os.path.join(VECTORS, fname)))
    return [g for g in j["testGroups"] if g.get("function") == function]


def cases(fname, function=None):
    return [pytest.param(g["parameterSet"], t, id=f"{g['parameterSet']}-tc{t['tcId']}")
            for g in groups(fname, function) for t in g["tests"]]


@pytest.mark.parametrize("ps,t", cases("acvp_mlkem_keygen.json"))
def test_acvp_keygen(ps, t):
    ek, dk = PARAMS[ps]().keygen_internal(bytes.fromhex(t["d"]), bytes.fromhex(t["z"]))
    assert ek.hex().upper() == t["ek"].upper()
    assert dk.hex().upper() == t["dk"].upper()


@pytest.mark.parametrize("ps,t", cases("acvp_mlkem_encapdecap.json", "encapsulation"))
def test_acvp_encaps(ps, t):
    K, c = PARAMS[ps]().encaps_internal(bytes.fromhex(t["ek"]), bytes.fromhex(t["m"]))
    assert c.hex().upper() == t["c"].upper()
    assert K.hex().upper() == t["k"].upper()


@pytest.mark.parametrize("ps,t", cases("acvp_mlkem_encapdecap.json", "decapsulation"))
def test_acvp_decaps(ps, t):
    K = PARAMS[ps]().decaps_internal(bytes.fromhex(t["dk"]), bytes.fromhex(t["c"]))
    assert K.hex().upper() == t["k"].upper()


@pytest.mark.parametrize("ps,t", cases("acvp_mlkem_encapdecap.json", "encapsulationKeyCheck"))
def test_acvp_ek_check(ps, t):
    assert PARAMS[ps]().ek_check(bytes.fromhex(t["ek"])) == t["testPassed"]


@pytest.mark.parametrize("ps,t", cases("acvp_mlkem_encapdecap.json", "decapsulationKeyCheck"))
def test_acvp_dk_check(ps, t):
    assert PARAMS[ps]().dk_check(bytes.fromhex(t["dk"])) == t["testPassed"]


@pytest.mark.parametrize("ps", PARAMSETS)
def test_vs_kyber_py(ps):
    from kyber_py.ml_kem import ML_KEM_512, ML_KEM_768
    ref = {"ML-KEM-512": ML_KEM_512, "ML-KEM-768": ML_KEM_768}[ps]
    kem = PARAMS[ps]()
    rng = random.Random(ps)
    for _ in range(20):
        d, z, m = (rng.randbytes(32) for _ in range(3))
        ek, dk = kem.keygen_internal(d, z)
        assert (ek, dk) == ref._keygen_internal(d, z)
        K, c = kem.encaps_internal(ek, m)
        assert (K, c) == ref._encaps_internal(ek, m)
        assert kem.decaps(dk, c) == K == ref.decaps(dk, c)
        bad = bytes([c[0] ^ 1]) + c[1:]                      # implicit rejection path
        assert kem.decaps(dk, bad) == ref.decaps(dk, bad) != K


# chip calls per operation, handoff section 2: (NTT, basemul, INTT) ; scale follows every INTT
CALLS = {("ML-KEM-512", "keygen"): (4, 4, 0), ("ML-KEM-768", "keygen"): (6, 9, 0),
         ("ML-KEM-512", "encaps"): (2, 6, 3), ("ML-KEM-768", "encaps"): (3, 12, 4),
         ("ML-KEM-512", "decaps"): (4, 8, 4), ("ML-KEM-768", "decaps"): (6, 15, 5)}


@pytest.mark.parametrize("ps", PARAMSETS)
def test_chip_call_counts(ps):
    rng = random.Random(7)
    be = CountingBackend(ReferenceBackend())
    kem = PARAMS[ps](be)
    for op in ("keygen", "encaps", "decaps"):
        if op == "keygen":
            ek, dk = kem.keygen_internal(rng.randbytes(32), rng.randbytes(32))
        elif op == "encaps":
            K, c = kem.encaps_internal(ek, rng.randbytes(32))
        else:
            kem.decaps(dk, c)
        n, b, i = CALLS[(ps, op)]
        assert be.counts == {"ntt": n, "basemul": b, "invntt": i, "scale": i}, (op, be.counts)
        be.counts = dict.fromkeys(be.counts, 0)
