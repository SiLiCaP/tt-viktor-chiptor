"""SHA-3 demo website: ML-KEM-512 with every hash call on the hash-only chip (chipathon-2026 branch sha3-only),
on the Pico 2 W + Tang Nano rig, with a live block diagram of which step runs when and where.

    python host/sha3_demo.py                       # the rig: Pico 2 W on /dev/ttyACM0 (auto), chip in the Tang Nano
    python host/sha3_demo.py --port /dev/ttyUSB1   # the Tang Nano alone over its USB UART
    python host/sha3_demo.py --sim                 # pin-level Python model of the chip, no board needed
    then open http://localhost:8080

The FPGA must hold the hash-only chip (docs/PICO_TANG_RIG.md, "The hash-only chip on the rig"). The PC plays the
RP2350: it runs ML-KEM-512 and sends every SHA3-256 (H), SHA3-512 (G), SHAKE256 (J, PRF) and SHAKE128 (XOF) call to
the chip as pin words; the PRF's SamplePolyCBD also runs on the chip (BURST_CBD). The NTT, matrix products,
rejection sampling and encoding stay on the PC / RP2350, as on the real board. Every result is checked against
hashlib; the key exchange against pure-software FIPS 203.

Tabs: the rig (live USB / wire traffic), the chip, hash anything, the ML-KEM-512 map (block diagram + timeline),
performance (measured here, predicted on the Tiny Tapeout board).
"""
import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "sim"), os.path.join(ROOT, "model")]

import mlkem as M  # noqa: E402
import route_model as RM  # noqa: E402
from hash_jobs import (ABSORB, ALGOS, BURST, BURST_CBD, CLEAR, PERMUTE, SKIP, SQUEEZE, HashJob,  # noqa: E402
                       hash_only_jobs, standard_jobs)
from tt_emu import DEPTH, SYNC, enc_load, enc_read_cap, enc_run  # noqa: E402

Q = 3329
F_CHIP, F_RP = 50e6, 150e6
PERM = 368                                    # keccak_ring K = 8 clocks per permutation
CHIP = {"top": "tt_um_NTT_Core (hash-only build, branch sha3-only)", "K": 8, "tiles": "3x2",
        "area_synth": 48568, "util": 55.5, "setup_ss": 8.17, "hold": 0.018, "lvs": 0, "drc": 0}


# ---------------- Keccak-f[1600] and a pin-level model of the hash-only chip ----------------
RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
      0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
      0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
      0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
      0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
MASK = (1 << 64) - 1


def keccak_f(A):
    """A[x + 5 y], 64-bit lanes."""
    for rc in RC:
        C = [A[x] ^ A[x + 5] ^ A[x + 10] ^ A[x + 15] ^ A[x + 20] for x in range(5)]
        D = [C[(x - 1) % 5] ^ (((C[(x + 1) % 5] << 1) | (C[(x + 1) % 5] >> 63)) & MASK) for x in range(5)]
        A = [A[i] ^ D[i % 5] for i in range(25)]
        B = [0] * 25
        for x in range(5):
            for y in range(5):
                r = ROT[x][y]
                v = A[x + 5 * y]
                B[y + 5 * ((2 * x + 3 * y) % 5)] = ((v << r) | (v >> (64 - r))) & MASK if r else v
        A = [B[i] ^ ((~B[(i % 5 + 1) % 5 + 5 * (i // 5)]) & B[(i % 5 + 2) % 5 + 5 * (i // 5)]) for i in range(25)]
        A[0] ^= rc
    return A


def cbd2(x):
    return (x & 1) + (x >> 1 & 1) - (x >> 2 & 1) - (x >> 3 & 1)


def cbd3(x):
    return (x & 1) + (x >> 1 & 1) + (x >> 2 & 1) - (x >> 3 & 1) - (x >> 4 & 1) - (x >> 5 & 1)


class ChipModel:
    """The hash-only chip at its pins (src/hash_io.v + keccak_ring, K = 8), one word per clock: the byte asked
    for by word k is on uo_out in sample k + 2, 0 otherwise. Stands in for the FPGA under --sim."""
    F_DUT = 13.5e6

    def __init__(self):
        self.port = "model"
        self.phase_s = {"tx": 0.0, "calc": 0.0, "rx": 0.0}
        self.A, self.ptr, self.p3, self.left2, self.left4 = [0] * 25, 0, 0, 0, 0
        self.states = []                          # state after each permutation, for the page

    def _byte(self, i):
        return self.A[i // 8] >> (8 * (i % 8)) & 0xFF

    def _out(self, raw, cbd, eta3):
        if not cbd:
            return raw
        s4 = lambda v: v & 15
        if not eta3:
            return s4(cbd2(raw >> 4)) << 4 | s4(cbd2(raw & 15))
        p = self.p3
        self.p3 = (p + 1) % 3
        if p == 0:
            self.left2 = raw >> 6
            return s4(cbd3(raw & 63))
        if p == 1:
            v = s4(cbd3((raw & 15) << 2 | self.left2))
            self.left4 = raw >> 4
            return v
        return s4(cbd3(raw >> 2)) << 4 | s4(cbd3((raw & 3) << 4 | self.left4))

    def run_stream(self, words):
        n = len(words)
        uo = [0] * (n + 3)
        burst_end = -1
        t0 = time.perf_counter()
        for k, w in enumerate(words):
            if k < burst_end:
                continue
            if not ((w >> 12) & 1 and (w >> 8) & 15 == 15):
                continue
            cmd, d = ((w >> 13) & 1) << 2 | (w >> 14) & 3, w & 0xFF
            if cmd == ABSORB:
                self.A[self.ptr // 8] ^= d << (8 * (self.ptr % 8))
                self.ptr += 1
            elif cmd == SQUEEZE:
                uo[k + 2] = self._byte(self.ptr)
                self.ptr += 1
            elif cmd == PERMUTE:
                self.A = keccak_f(self.A)
                self.states.append(list(self.A))
                self.states = self.states[-8:]
                self.ptr = 0
            elif cmd == CLEAR:
                self.A, self.ptr, self.p3 = [0] * 25, 0, 0
            elif cmd == SKIP:
                self.ptr += 8
            elif cmd in (BURST, BURST_CBD):
                nb = 8 * (d & 31)
                cbd, eta3 = cmd == BURST_CBD, bool(d & 0x80)
                for j in range(nb):
                    uo[k + 2 + j] = self._out(self._byte(self.ptr), cbd, eta3)
                    self.ptr += 1
                burst_end = k + nb
        self.phase_s["calc"] += time.perf_counter() - t0
        return [(uo[k], 0, 0) for k in range(n)]

    def set_inputs(self, *_):
        pass

    def reset(self, *_):
        self.A, self.ptr, self.p3 = [0] * 25, 0, 0


# ---------------- the rig tap: what every batch does on the USB link ----------------
class RigTap:
    """Records each chip call's LOAD / RUN / READ_CAP traffic: the real bytes and, on hardware, the measured
    time of each phase (modelled at 1 Mbaud, DUT 13.5 MHz under --sim)."""

    def __init__(self, emu, real, mode):
        self.emu, self.real, self.mode = emu, real, mode
        self.label = None
        self.seq, self.hist = 0, []
        self.totals = {"out": 0, "in": 0, "cmds": 0, "batches": 0, "clocks": 0}

    def run_stream(self, words):
        words = list(words)
        before = dict(self.emu.phase_s)
        caps = self.emu.run_stream(words)
        chunks = [(i, words[i:i + DEPTH]) for i in range(0, len(words), DEPTH)]
        load = b"".join(enc_load(0, c) for _, c in chunks)
        run = b"".join(enc_run(len(c)) for _, c in chunks)
        rd = b"".join(enc_read_cap(0, len(c)) for _, c in chunks)
        cap_n = sum(2 + 3 * len(c) for _, c in chunks)
        n_out, n_in = len(load) + len(run) + len(rd), 4 * len(chunks) + cap_n
        first = next((i for i, c in enumerate(caps) if c[0]), 0)
        if self.real:
            t = {k: self.emu.phase_s[k] - before.get(k, 0.0) for k in ("tx", "calc", "rx")}
        else:
            bt = 10 / 1e6
            t = {"tx": (len(load) + 2) * bt, "calc": len(words) / ChipModel.F_DUT + (len(run) + 2) * bt,
                 "rx": (len(rd) + cap_n) * bt}
        self.seq += 1
        for k, v in (("out", n_out), ("in", n_in), ("cmds", 3 * len(chunks)), ("batches", 1), ("clocks", len(words))):
            self.totals[k] += v
        self.hist.append({"seq": self.seq, "op": self.label or "hash", "words": len(words), "t": t,
                          "load": load[:22].hex(), "load_n": len(load), "run": run.hex()[:16], "rd": rd.hex()[:16],
                          "cap_n": cap_n, "cap_first": first,
                          "cap_res": bytes(c[0] for c in caps[first:first + 16]).hex()})
        self.hist = self.hist[-30:]
        return caps

    def state(self):
        return {"seq": self.seq, "hist": self.hist[-12:], "totals": self.totals, "real": self.real,
                "mode": self.mode, "port": getattr(self.emu, "port", "?"), "f_dut": ChipModel.F_DUT}


# ---------------- the hash chip as ML-KEM sees it ----------------
class HashChip:
    """Runs one sponge on the chip per call, checks it against hashlib, and keeps the trace for the page."""

    def __init__(self, rig, on_call=None):
        self.rig, self.on_call = rig, on_call
        self.calls, self.mismatch = [], 0
        self.last_pins = None

    def sponge(self, name, msg, outlen=None, cbd_eta=None, label=None):
        job = HashJob(name, msg, 8, burst=True, skip=True, cbd_eta=cbd_eta, outlen=outlen)
        words, sq = job.words()
        self.rig.label = label or name
        t = time.perf_counter()
        caps = self.rig.run_stream(words)
        wall = time.perf_counter() - t
        samples = [c[0] for c in caps]
        got = job.collect(samples, sq)
        ok = got == job.expected()
        self.mismatch += not ok
        rate = ALGOS[name][0]
        perms = (len(msg) + 1 + rate - 1) // rate + (job.outlen + rate - 1) // rate - 1
        host_words = sum(1 for w in words if w)
        rec = {"name": name, "label": label or name, "in": len(msg), "out": job.outlen, "cbd": cbd_eta,
               "clocks": len(words), "perms": perms, "host_words": host_words, "ok": ok, "wall_s": wall,
               "board_s": len(words) / F_CHIP + RM.SETUP_S + (host_words * 2 + job.outlen * 2) / F_RP}
        self.calls.append(rec)
        first = next((i for i, v in enumerate(samples) if v), len(words))
        head = min(len(words), 48, max(first - 6, 0))
        lo = max(head, first - 6)
        self.last_pins = {"label": rec["label"], "stim": words[:head] + words[lo:lo + 140],
                          "uo": samples[:head] + samples[lo:lo + 140], "gap": head if lo > head else None,
                          "skipped": lo - head, "n": len(self.calls)}
        if self.on_call:
            self.on_call(rec)
        if not ok:
            raise RuntimeError(f"chip {name} result differs from hashlib")
        return got

    # the FIPS 203 functions
    def H(self, s, label="H"):
        return self.sponge("sha3_256", s, label=label)

    def J(self, s, label="J"):
        return self.sponge("shake_256", s, outlen=32, label=label)

    def G(self, s, label="G"):
        h = self.sponge("sha3_512", s, label=label)
        return h[:32], h[32:]

    def PRF_CBD(self, eta, s, b, label="PRF"):
        """PRF_eta(s, b) = SHAKE256(s || b, 64 eta), through SamplePolyCBD on the chip: coefficients mod q."""
        f = self.sponge("shake_256", s + bytes([b]), cbd_eta=eta, label=label)
        return [x % Q for x in f]

    def XOF(self, B, nbytes, label="XOF"):
        return self.sponge("shake_128", B, outlen=nbytes, label=label)


def reject(buf):
    """SampleNTT's rejection loop over XOF bytes (the RP2350's part); None if 256 were not reached."""
    a = []
    for p in range(0, len(buf) - 2, 3):
        d1 = buf[p] + 256 * (buf[p + 1] % 16)
        d2 = buf[p + 1] // 16 + 16 * buf[p + 2]
        if d1 < Q:
            a.append(d1)
        if d2 < Q and len(a) < 256:
            a.append(d2)
        if len(a) == 256:
            return a
    return None


# ---------------- ML-KEM-512, traced block by block ----------------
class TracedMLKEM(M.MLKEM):
    """ML-KEM-512 (FIPS 203) with each block of the diagram traced: which block, on the chip or on the RP2350,
    when, and what went in and out. Hashing goes to the chip; the arithmetic runs here (the RP2350's job)."""

    def __init__(self, chip, tracer):
        super().__init__(2, 3, 2, 10, 4, M.ReferenceBackend())
        self.chip, self.tr = chip, tracer

    def _sample_ntt(self, B, label, block):
        n = 504
        while True:
            buf = self.chip.XOF(B, n, label=label)
            with self.tr.step(block.replace("xof", "rej"), "rp", f"SampleNTT {label[4:]}", cat="rej"):
                a = reject(buf)
            if a:
                return a
            n += 168                          # one more SHAKE128 block (rare)

    def _matrix_traced(self, rho, pre, transpose=False):
        A = [[None] * 2 for _ in range(2)]
        with self.tr.step(f"{pre}_xof", "chip", "XOF(ρ, j, i) → Â", cat="xof"):
            for i in range(2):
                for j in range(2):
                    A[i][j] = self._sample_ntt(rho + bytes([j, i]), f"XOF Â[{i}][{j}]", f"{pre}_xof")
        return [list(r) for r in zip(*A)] if transpose else A

    def kpke_keygen(self, d):
        tr = self.tr
        with tr.step("kg_G", "chip", "G(d ‖ k) → ρ, σ", cat="g"):
            rho, sigma = self.chip.G(d + bytes([self.k]), label="G(d‖k)")
        tr.note(rho=rho.hex(), sigma=sigma.hex())
        A = self._matrix_traced(rho, "kg")
        with tr.step("kg_prf", "chip", "PRF(σ, N) → CBD → s, e", cat="prf"):
            s = [self.chip.PRF_CBD(3, sigma, n, label=f"PRF→CBD s[{n}]") for n in range(2)]
            e = [self.chip.PRF_CBD(3, sigma, 2 + n, label=f"PRF→CBD e[{n}]") for n in range(2)]
        with tr.step("kg_ntt", "rp", "NTT(s), NTT(e)", cat="ntt", ntt=4):
            s_hat = [self.be.ntt(p) for p in s]
            e_hat = [self.be.ntt(p) for p in e]
        with tr.step("kg_mv", "rp", "t̂ = Â∘ŝ + ê", cat="mv", basemul=4):
            t_hat = [M.padd(self._dot(A[i], s_hat), e_hat[i]) for i in range(2)]
        with tr.step("kg_enc", "rp", "ByteEncode12 → ek, dk", cat="enc"):
            ek = b"".join(M.byte_encode(t, 12) for t in t_hat) + rho
            dk = b"".join(M.byte_encode(x, 12) for x in s_hat)
        tr.keep(A=A, s=s, e=e, t_hat=t_hat)
        return ek, dk

    def kpke_encrypt(self, ek, m, r, pre="en"):
        tr = self.tr
        t_hat = [M.byte_decode(ek[384 * i:384 * (i + 1)], 12) for i in range(2)]
        rho = ek[768:800]
        At = self._matrix_traced(rho, pre, transpose=True)
        with tr.step(f"{pre}_prf", "chip", "PRF(r, N) → CBD → y, e₁, e₂", cat="prf"):
            y = [self.chip.PRF_CBD(3, r, n, label=f"PRF→CBD y[{n}]") for n in range(2)]
            e1 = [self.chip.PRF_CBD(2, r, 2 + n, label=f"PRF→CBD e1[{n}]") for n in range(2)]
            e2 = self.chip.PRF_CBD(2, r, 4, label="PRF→CBD e2")
        with tr.step(f"{pre}_ntt", "rp", "NTT(y)", cat="ntt", ntt=2):
            y_hat = [self.be.ntt(p) for p in y]
        with tr.step(f"{pre}_mv", "rp", "u = NTT⁻¹(Âᵀ∘ŷ) + e₁ · v = NTT⁻¹(t̂ᵀ∘ŷ) + e₂ + μ", cat="mv",
                     basemul=6, invntt=3):
            u = [M.padd(self._intt(self._dot(At[i], y_hat)), e1[i]) for i in range(2)]
            mu = [M.decompress(b, 1) for b in M.byte_decode(m, 1)]
            v = M.padd(M.padd(self._intt(self._dot(t_hat, y_hat)), e2), mu)
        with tr.step(f"{pre}_enc", "rp", "Compress, ByteEncode → c", cat="enc"):
            c1 = b"".join(M.byte_encode([M.compress(x, 10) for x in p], 10) for p in u)
            c2 = M.byte_encode([M.compress(x, 4) for x in v], 4)
        return c1 + c2

    def kpke_decrypt(self, dk, c):
        tr = self.tr
        with tr.step("de_dec", "rp", "ByteDecode, Decompress c → u, v", cat="enc"):
            u = [[M.decompress(x, 10) for x in M.byte_decode(c[320 * i:320 * (i + 1)], 10)] for i in range(2)]
            v = [M.decompress(x, 4) for x in M.byte_decode(c[640:], 4)]
            s_hat = [M.byte_decode(dk[384 * i:384 * (i + 1)], 12) for i in range(2)]
        with tr.step("de_ntt", "rp", "NTT(u)", cat="ntt", ntt=2):
            u_hat = [self.be.ntt(p) for p in u]
        with tr.step("de_mv", "rp", "w = v − NTT⁻¹(ŝᵀ∘û)", cat="mv", basemul=2, invntt=1):
            w = M.psub(v, self._intt(self._dot(s_hat, u_hat)))
        with tr.step("de_m", "rp", "m′ = ByteEncode1(Compress1(w))", cat="enc"):
            return M.byte_encode([M.compress(x, 1) for x in w], 1)

    def keygen_internal(self, d, z):
        ek, dk_pke = self.kpke_keygen(d)
        with self.tr.step("kg_H", "chip", "H(ek) → part of dk", cat="h"):
            h = self.chip.H(ek, label="H(ek)")
        return ek, dk_pke + ek + h + z

    def encaps_internal(self, ek, m):
        with self.tr.step("en_H", "chip", "H(ek)", cat="h"):
            h = self.chip.H(ek, label="H(ek)")
        with self.tr.step("en_G", "chip", "G(m ‖ H(ek)) → K, r", cat="g"):
            K, r = self.chip.G(m + h, label="G(m‖h)")
        return K, self.kpke_encrypt(ek, m, r)

    def decaps_internal(self, dk, c):
        dk_pke, ek, h, z = dk[:768], dk[768:1568], dk[1568:1600], dk[1600:1632]
        m2 = self.kpke_decrypt(dk_pke, c)
        with self.tr.step("de_G", "chip", "G(m′ ‖ h) → K′, r′", cat="g"):
            K2, r2 = self.chip.G(m2 + h, label="G(m′‖h)")
        with self.tr.step("de_J", "chip", "J(z ‖ c) → K̄ (rejection key)", cat="j"):
            Kbar = self.chip.J(z + c, label="J(z‖c)")
        c2 = self.kpke_encrypt(ek, m2, r2, pre="re")
        with self.tr.step("de_cmp", "rp", "c = c′ ? K′ : K̄ (constant-time select)", cat="cmp"):
            return K2 if c == c2 else Kbar


class Tracer:
    """Collects the steps of one operation; the page highlights the running one."""

    def __init__(self, app):
        self.app, self.steps, self.op, self.kept, self.notes = app, [], None, {}, {}
        self.cur = None

    def step(self, block, where, title, cat, **counts):
        tr = self

        class Ctx:
            def __enter__(self):
                tr.cur = {"block": block, "where": where, "title": title, "cat": cat, "op": tr.op,
                          "t0": time.perf_counter(), "calls": [], **counts}
                tr.app.on_step(tr.cur)
                return tr.cur

            def __exit__(self, *exc):
                s = tr.cur
                s["dt"] = time.perf_counter() - s["t0"]
                tr.steps.append(s)
                time.sleep(tr.app.slowmo)         # slow motion: the block stays lit on the page
                tr.cur = None
                tr.app.on_step(None)
                tr.app.status["done"].append([s["op"], s["block"]])
                return False
        if self.cur is not None:                  # nested (XOF inside the matrix step): record as part of it
            class Nest:
                def __enter__(self_):
                    self_.t = time.perf_counter()
                    self_.prev = tr.cur
                    return tr.cur

                def __exit__(self_, *exc):
                    prev = self_.prev
                    prev.setdefault("rej_s", 0.0)
                    prev["rej_s"] += time.perf_counter() - self_.t
                    return False
            return Nest()
        return Ctx()

    def call(self, rec):
        if self.cur is not None:
            self.cur["calls"].append(rec)

    def keep(self, **kw):
        self.kept.update(kw)

    def note(self, **kw):
        self.notes.update(kw)


# ---------------- board-time model per step (the Tiny Tapeout board: RP2350 150 MHz + chip 50 MHz) ----------------
def _profile():
    path = os.path.join(ROOT, "tools", "mlkem_profile", "profile.json")
    return json.load(open(path))["table"]


def board_times(op, steps):
    """Each step's predicted time on the TT board. Chip steps: their exact clocks at 50 MHz plus the RP2350's
    setup and an optimized PIO / DMA feed (sim/route_model.py). RP2350 steps: the NTT family from cited pqm4
    cycles; everything else shares the RP2350's remaining non-hash time (pqm4 totals) by the instruction profile
    (tools/mlkem_profile), with CBD removed because the chip does it. A model, not a measurement."""
    total, hashing = RM.rp(op)
    arith = sum(n * RM.SW_CYC[k] for k, n in RM.NTT_CALLS[op].items()) / F_RP
    rest = total - hashing - arith
    prof = _profile()[op]
    cat_instr = {"rej": prof["rejection sampling (SampleNTT)"],
                 "enc": prof["encode / decode (ByteEncode12, msg)"] + prof["compress / decompress"],
                 "mv": prof["polynomial add / sub / reduce"], "cmp": prof["FO compare + select (verify, cmov)"]}
    spread = prof["memcpy / memset"] + prof["other (KEM glue)"]
    base = sum(cat_instr.values()) + spread + prof["CBD sampling (SamplePolyCBD)"]
    rest_cat = {k: rest * (v + spread * v / max(1, sum(cat_instr.values()))) / base for k, v in cat_instr.items()}
    rp_steps = [s for s in steps if s["where"] == "rp"]
    n_cat = {k: sum(1 for s in rp_steps if s["cat"] == k) for k in rest_cat}
    for s in steps:
        if s["where"] == "chip":
            s["board_s"] = sum(c["board_s"] for c in s["calls"])
            if s["cat"] == "xof":                 # the rejection loops run on the RP2350 between the XOF calls
                s["board_rej_s"] = rest_cat["rej"] / max(1, sum(1 for t in steps if t["cat"] == "xof"))
        else:
            a = (s.get("ntt", 0) * RM.SW_CYC["ntt"] + s.get("invntt", 0) * RM.SW_CYC["invntt"]
                 + s.get("basemul", 0) * RM.SW_CYC["basemul"]) / F_RP
            s["board_s"] = a + (rest_cat.get(s["cat"], 0) / n_cat[s["cat"]] if n_cat.get(s["cat"]) else 0)
    return {"rp2350_alone_s": total, "rp2350_hash_s": hashing}


# ---------------- the app ----------------
class Demo:
    SECTIONS = ("hash", "kem", "perf")

    def __init__(self, emu, source, real, mode):
        self.lock = threading.Lock()
        self.rig = RigTap(emu, real, mode)
        self.chip = HashChip(self.rig, on_call=self._on_call)
        self.slowmo = 0.0
        self.tracer = None
        self.status = {"source": source, "busy": None, "step": None, "log": [], "pins": None,
                       "ver": {s: 0 for s in self.SECTIONS}, "calls_total": 0, "clocks_total": 0,
                       "rig": self.rig.state(), "chip": CHIP, "slowmo": 0, "done": []}
        self.data = {s: {} for s in self.SECTIONS}
        self.publish("perf", perf_model())

    def _on_call(self, rec):
        self.status["calls_total"] += 1
        self.status["clocks_total"] += rec["clocks"]
        self.status["pins"] = self.chip.last_pins
        self.status["rig"] = self.rig.state()
        if self.tracer:
            self.tracer.call(rec)
        if self.status["step"]:
            self.status["step"]["calls"] = self.status["step"].get("calls", 0) + 1
            self.status["step"]["last"] = rec["label"]

    def on_step(self, s):
        self.status["step"] = None if s is None else {"block": s["block"], "where": s["where"], "title": s["title"],
                                                      "op": s["op"], "calls": 0}

    def log(self, who, msg, kind="info"):
        self.status["log"].append({"t": time.strftime("%H:%M:%S"), "who": who, "msg": msg, "kind": kind})
        self.status["log"] = self.status["log"][-80:]

    def publish(self, section, payload):
        self.data[section] = payload
        self.status["ver"][section] += 1

    # ---- actions ----
    def hash(self, args):
        name = args.get("algo", "sha3_256")
        msg = (args.get("msg") or "").encode()[:2000]
        outlen = {"shake_128": 32, "shake_256": 32}.get(name)
        t = time.perf_counter()
        got = self.chip.sponge(name, msg, outlen=outlen, label=name.upper().replace("_", "-"))
        wall = time.perf_counter() - t
        rec = self.chip.calls[-1]
        rate = ALGOS[name][0]
        blocks = (len(msg) + 1 + rate - 1) // rate
        self.publish("hash", {"algo": name, "msg": msg.decode(errors="replace"), "digest": got.hex(),
                              "ref": hashlib.new(name, msg).hexdigest() if name.startswith("sha3")
                              else hashlib.new(name, msg).hexdigest(outlen),
                              "ok": rec["ok"], "clocks": rec["clocks"], "perms": rec["perms"], "rate": rate,
                              "blocks": blocks, "in": len(msg), "out": rec["out"], "wall_s": wall,
                              "chip_us": rec["clocks"] / F_CHIP * 1e6, "host_words": rec["host_words"],
                              "absorb_clocks": len(msg) + 1 + 8, "perm_clocks": rec["perms"] * (PERM + 1),
                              "pins": self.chip.last_pins})
        self.log("chip", f"{name}: {len(msg)} bytes in, {rec['out']} out, {rec['clocks']} clocks "
                 f"({rec['clocks'] / F_CHIP * 1e6:.1f} µs at 50 MHz) · " + ("equals hashlib ✓" if rec["ok"] else "MISMATCH"),
                 "ok" if rec["ok"] else "bad")

    def exchange(self, args):
        self.slowmo = float(args.get("slowmo", 0) or 0)
        self.status["done"] = []
        self.publish("kem", {"ops": {}, "partial": True})
        self.status["slowmo"] = self.slowmo
        rng = random.SystemRandom()
        d, z, m = rng.randbytes(32), rng.randbytes(32), rng.randbytes(32)
        out = {"ops": {}, "d": d.hex(), "z": z.hex(), "m": m.hex()}
        res = {}
        c0 = len(self.chip.calls)
        for op in ("keygen", "encaps", "decaps"):
            self.tracer = Tracer(self)
            self.tracer.op = op
            kem = TracedMLKEM(self.chip, self.tracer)
            t = time.perf_counter()
            if op == "keygen":
                res["ek"], res["dk"] = kem.keygen_internal(d, z)
            elif op == "encaps":
                res["K_bob"], res["c"] = kem.encaps_internal(res["ek"], m)
            else:
                res["K_alice"] = kem.decaps_internal(res["dk"], res["c"])
            wall = time.perf_counter() - t
            steps = self.tracer.steps
            base = steps[0]["t0"] if steps else t
            for s in steps:
                s["t0"] -= base
            model = board_times(op, steps)
            out["ops"][op] = {"steps": steps, "wall_s": wall, **model,
                              "board_s": sum(s["board_s"] + s.get("board_rej_s", 0) for s in steps)}
            if op == "keygen":
                out["rho"], out["sigma"] = self.tracer.notes.get("rho"), self.tracer.notes.get("sigma")
                k = self.tracer.kept
                out["A"] = k["A"]
                out["s"] = [[x - Q if x > Q // 2 else x for x in p] for p in k["s"]]
            self.publish("kem", dict(out, partial=True))
            self.log("demo", f"{op}: {len(steps)} steps, {sum(len(s['calls']) for s in steps)} hash calls on the chip, "
                     f"{wall:.2f} s on this rig")
        self.tracer = None
        ref = M.MLKEM512()
        ek, dk = ref.keygen_internal(d, z)
        K, c = ref.encaps_internal(ek, m)
        std = (ek, dk, K, c) == (res["ek"], res["dk"], res["K_bob"], res["c"])
        calls = self.chip.calls[c0:]
        out.update({"ek": res["ek"].hex(), "c": res["c"].hex(), "K_bob": res["K_bob"].hex(),
                    "K_alice": res["K_alice"].hex(), "match": res["K_bob"] == res["K_alice"], "standard": std,
                    "hash_calls": len(calls), "hash_clocks": sum(x["clocks"] for x in calls),
                    "hash_ok": all(x["ok"] for x in calls), "partial": False})
        self.publish("kem", out)
        self.log("Alice", ("shared keys match ✓" if out["match"] else "keys DIFFER ✗") +
                 (" · identical to pure-software FIPS 203 ✓" if std else " · differs from FIPS 203 ✗") +
                 f" · {len(calls)} hash calls, every one equal to hashlib", "ok" if out["match"] and std else "bad")
        self.slowmo = 0.0

    def selftest(self, _):
        jobs = standard_jobs(8) + hash_only_jobs(8)
        bad = 0
        t = time.perf_counter()
        for j in jobs:
            self.rig.label = f"selftest {j.name}"
            words, sq = j.words()
            s = [c[0] for c in self.rig.run_stream(words)]
            bad += j.collect(s, sq) != j.expected()
        self.status["rig"] = self.rig.state()
        self.log("chip", f"self-test: {len(jobs) - bad}/{len(jobs)} jobs (every algorithm, bursts, CBD) bit-exact "
                 f"in {time.perf_counter() - t:.1f} s", "ok" if not bad else "bad")

    ACTIONS = {"hash": hash, "exchange": exchange, "selftest": selftest}

    def run(self, action, args):
        if self.status["busy"]:
            return False
        self.status["busy"] = action

        def work():
            try:
                with self.lock:
                    self.ACTIONS[action](self, args)
            except Exception as e:
                self.log("demo", f"{action}: {e}", "bad")
            finally:
                self.status["busy"] = None
                self.status["step"] = None
                self.status["rig"] = self.rig.state()
        threading.Thread(target=work, daemon=True).start()
        return True


def perf_model():
    """The speed tab: ML-KEM-512 per exchange on the TT board (sim/route_model.py)."""
    rows = [("RP2350 alone", None, "optimized", False, False),
            ("+ hash chip K = 8, firmware as written", "ring K=8", "as written", True, True),
            ("+ hash chip K = 8, optimized PIO feed", "ring K=8", "optimized", True, True),
            ("+ hash chip K = 16, optimized PIO feed (if it fits 3×2)", "ring K=16", "optimized", True, True)]
    out = []
    base = RM.exchange()
    for name, core, feed, burst, cbd in rows:
        t = RM.exchange(core, feed, burst=burst, cbd=cbd) if core else base
        out.append({"name": name, "s": t, "x": base / t})
    ops = {op: {"total_s": RM.rp(op)[0], "hash_s": RM.rp(op)[1]} for op in RM.CALLS}
    return {"rows": out, "ops": ops}


def make_handler(app):
    def page():
        return open(os.path.join(HERE, "sha3_demo.html"), "rb").read()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/?"):
                init = json.dumps({"status": app.status, "data": app.data}).replace("</", "<\\/")
                self._send(page().replace(b"</head>", f"<script>window.__INIT = {init};</script></head>".encode(), 1),
                           "text/html; charset=utf-8")
            elif self.path == "/api/status":
                self._send(json.dumps(app.status).encode(), "application/json")
            elif self.path.startswith("/api/data/"):
                sec = self.path.rsplit("/", 1)[1]
                if sec not in app.data:
                    return self.send_error(404)
                self._send(json.dumps(app.data[sec]).encode(), "application/json")
            else:
                self.send_error(404)

        def do_POST(self):
            action = self.path[len("/api/"):] if self.path.startswith("/api/") else ""
            if action not in Demo.ACTIONS:
                return self.send_error(404)
            n = int(self.headers.get("Content-Length", 0) or 0)
            args = json.loads(self.rfile.read(n) or b"{}") if n else {}
            self._send(json.dumps({"started": app.run(action, args)}).encode(), "application/json")
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="pin-level Python model of the chip instead of the board")
    ap.add_argument("--port", help="serial port: the Pico 2 W (/dev/ttyACM0, default if present) or the Tang Nano")
    ap.add_argument("--http", type=int, default=8080)
    ap.add_argument("--check", action="store_true", help="run the self-test and a key exchange, print, exit")
    a = ap.parse_args()
    if a.sim:
        emu, source, real, mode = ChipModel(), "pin-level model of the hash chip (no board)", False, "sim"
    else:
        from tt_emu import TTEmu
        port = a.port or ("/dev/ttyACM0" if os.path.exists("/dev/ttyACM0") else None)
        emu = TTEmu(port)
        emu.ping()
        emu.set_inputs(0, 0)
        emu.reset(10)
        mode = "pico" if "ACM" in emu.port else "tang"
        probe = HashJob("sha3_256", b"abc", 8, burst=True)
        w, sq = probe.words()
        if probe.collect([c[0] for c in emu.run_stream(w)], sq) != probe.expected():
            sys.exit(f"{emu.port} answers, but the FPGA does not hold the hash-only chip (it loses its image when "
                     f"power-cycled). Load it:\n  make -C fpga prog {'TARGET=pico ' if mode == 'pico' else ''}GL=0 "
                     f"DESIGN_ROOT=~/tools/work/br/sha3-only BUILD_TAG=_hashonly_k8 "
                     f"CHPARAM='chparam -set CLOCK_GATING 0 keccak_ring;'")
        source = (f"Pico 2 W on {emu.port} → 26 wires → Tang Nano" if mode == "pico"
                  else f"Tang Nano on {emu.port}") + " · hash-only chip (sha3-only, RTL)"
        real = True
    app = Demo(emu, source, real, mode)
    app.log("demo", f"chip: {source}")
    if a.check:
        app.selftest({})
        app.exchange({})
        for l in app.status["log"]:
            print(l["who"], l["msg"])
        k = app.data["kem"]
        print({op: f"{v['wall_s']:.2f} s here, {v['board_s'] * 1e3:.3f} ms on the TT board (model)"
               for op, v in k["ops"].items()})
        sys.exit(0 if k["match"] and k["standard"] else 1)
    srv = ThreadingHTTPServer(("127.0.0.1", a.http), make_handler(app))
    print(f"SHA-3 demo ({source}) at http://localhost:{a.http}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
