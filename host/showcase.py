"""Showcase website: click through ML-KEM-512 on our NTT chip and see the real data at every step.

    python host/showcase.py            # chip on the Tang Nano (auto-detected)
    python host/showcase.py --sim      # Python chip model, no board needed
    then open http://localhost:8080

Sections: live chip pins, polynomial multiply with an NTT layer-by-layer view, the full key exchange
with the actual matrix / secret / keys / ciphertext bytes, an encrypted message, Eve's attacks
(pin snooping vs masking, tampering, timing), and measured vs predicted performance.
Every NTT / basemul / scale runs on the chip; hashing and encoding run on the PC (the RP2350's job).
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
sys.path[:0] = [HERE, os.path.join(ROOT, "sim"), os.path.join(ROOT, "model"), os.path.join(ROOT, "tools")]

import perf_model as PM  # noqa: E402
from board import BoardBackend, MaskedBackend, SimEmu  # noqa: E402
from mlkem import G, PARAMS, PRF, ReferenceBackend, TimingBackend, byte_decode, sample_poly_cbd  # noqa: E402
from mlkem_ntt_model import Q, polymul_schoolbook  # noqa: E402
from packet import open_, seal  # noqa: E402
from tt_emu import DEPTH, SYNC, enc_load, enc_read_cap, enc_run  # noqa: E402

PS = "ML-KEM-512"


def KEM(backend=None):
    return PARAMS[PS](backend)


def centered(p):
    return [x - Q if x > Q // 2 else x for x in p]


def system_timeline():
    """Predicted timeline of one ML-KEM-512 key exchange on the TT board (RP2350 + our chip): the real order
    of chip calls from a model run, host gaps apportioned by the measured Python gaps and scaled to the
    cited RP2350 host time, chip calls from sim/perf_model.py (PIO+DMA)."""
    class Rec:
        def __init__(self):
            self.inner, self.factor, self.ev = ReferenceBackend(), 1, []

        def __getattr__(self, name):
            fn = getattr(self.inner, name)

            def call(*a):
                self.ev.append(("call", name, time.perf_counter()))
                r = fn(*a)
                self.ev.append(("ret", name, time.perf_counter()))
                return r
            return call
    rng = random.Random(5)
    d, z, m = (rng.randbytes(32) for _ in range(3))
    out = {"ops": {}, "f_chip_mhz": PM.f_chip()[0] / 1e6}
    rec = Rec()
    kem = KEM(rec)
    state = {}
    for op in ("keygen", "encaps", "decaps"):
        rec.ev = []
        t0 = time.perf_counter()
        if op == "keygen":
            state["ek"], state["dk"] = kem.keygen_internal(d, z)
        elif op == "encaps":
            state["K"], state["c"] = kem.encaps_internal(state["ek"], m)
        else:
            kem.decaps(state["dk"], state["c"])
        t1 = time.perf_counter()
        # host gaps between chip calls (Python timing), then scaled to the RP2350's cited host time
        gaps, names, last = [], [], t0
        for kind, name, t in rec.ev:
            if kind == "call":
                gaps.append(t - last)
                names.append(name)
            else:
                last = t
        gaps.append(t1 - last)
        calls = {n: names.count(n) for n in ("ntt", "invntt", "basemul", "scale")}
        host_total = PM.rp2350_host_s(PS, op, calls)
        scale = host_total / sum(gaps)
        segs, t = [], 0.0
        for i, g in enumerate(gaps):
            if g * scale > 0:
                segs.append({"kind": "host", "name": "RP2350: hashing, sampling, encoding", "start": t, "dur": g * scale})
                t += g * scale
            if i < len(names):
                b = PM.chip_call_breakdown(names[i], 1, "pio_dma")
                segs.append({"kind": "chip", "name": names[i], "start": t, "dur": b["total_s"], "pins": b["pins_s"]})
                t += b["total_s"]
        out["ops"][op] = {"segments": segs, "total": t, "sw_total": PM.rp2350_sw_s(PS, op), "calls": calls}
    out["ntt_detail"] = PM.silicon_breakdown("ntt")
    out["ntt_detail"]["total_dma"] = PM.chip_call_breakdown("ntt", 1, "pio_dma")["total_s"]
    return out


class RigTap:
    """Sits between the chip backend and the Tang Nano driver (or the simulator) and records what each
    batch does on the USB-UART: the LOAD / RUN / READ_CAP commands, their bytes and how long each took.
    On the board the times are measured; in --sim they are modelled (10 bits per byte, DUT at 13.5 MHz)."""
    F_DUT = 27e6 / 2

    def __init__(self, emu, baud, real):
        self.emu, self.baud, self.real = emu, baud, real
        self.phase_s = emu.phase_s
        self.op, self.layer = None, 0
        self.seq, self.hist = 0, []
        self.totals = {"out": 0, "in": 0, "cmds": 0, "batches": 0}

    def __getattr__(self, name):
        return getattr(self.emu, name)

    def run_stream(self, words):
        words = list(words)
        before = dict(self.emu.phase_s)
        caps = self.emu.run_stream(words)
        chunks = [(i, words[i:i + DEPTH]) for i in range(0, len(words), DEPTH)]
        load = b"".join(enc_load(0, c) for _, c in chunks)
        run = b"".join(enc_run(len(c)) for _, c in chunks)
        rd = b"".join(enc_read_cap(0, len(c)) for _, c in chunks)
        cap = b"".join(bytes([SYNC, 0]) + bytes(v & 0xFF for t in caps[i:i + len(c)] for v in t) for i, c in chunks)
        ack = bytes([SYNC, 0])
        first = next((i for i, c in enumerate(caps) if c[0]), 0)       # results start after the pipeline delay
        cap_res = bytes(v & 0xFF for t in caps[first:first + 8] for v in t)
        n_out, n_in = len(load) + len(run) + len(rd), 4 * len(chunks) + len(cap)
        if self.real:
            t = {k: self.emu.phase_s[k] - before.get(k, 0.0) for k in ("tx", "calc", "rx")}
        else:
            bt = 10 / self.baud
            t = {"tx": (len(load) + 2) * bt, "calc": len(words) / self.F_DUT + (len(run) + 2) * bt,
                 "rx": (len(rd) + len(cap)) * bt}
        self.seq += 1
        self.totals["out"] += n_out
        self.totals["in"] += n_in
        self.totals["cmds"] += 3 * len(chunks)
        self.totals["batches"] += 1
        self.hist.append({"seq": self.seq, "op": self.op, "layer": self.layer, "words": len(words),
                          "out": n_out, "in": n_in, "t": t,
                          "load": load[:22].hex(), "load_n": len(load), "run": run.hex(), "rd": rd.hex(),
                          "ack": ack.hex(), "cap": cap[:26].hex(), "cap_n": len(cap),
                          "cap_first": first, "cap_res": cap_res.hex()})
        self.hist = self.hist[-30:]
        self.layer += 1
        return caps

    def state(self):
        return {"seq": self.seq, "hist": self.hist[-12:], "totals": self.totals, "baud": self.baud,
                "real": self.real, "port": getattr(self.emu, "port", "?"), "f_dut": self.F_DUT}


class Showcase:
    SECTIONS = ("polymul", "kex", "packet", "eve", "perf", "system")

    def __init__(self, emu, source, baud=1000000):
        self.lock = threading.Lock()
        self.source = source
        self.rig = RigTap(emu, baud, real=not isinstance(emu, SimEmu))
        self.chip = BoardBackend(self.rig)
        self.chip.on_call = self._on_call
        self.chip.on_batch = self._on_batch
        self.chip.on_layer = self._on_layer
        self.masked = False
        self.status = {"source": source, "ps": PS, "busy": None, "progress": {}, "log": [], "masked": False,
                       "pins": None, "ver": {s: 0 for s in self.SECTIONS}, "calls_total": 0, "clocks_total": 0,
                       "rig": self.rig.state()}
        self.data = {s: {} for s in self.SECTIONS}
        self.layers = None
        self.kex = {}
        self.publish("system", system_timeline())

    # ---------------- hooks from the chip backend ----------------
    def _on_call(self, name):
        pr = self.status["progress"]
        pr["calls"] = pr.get("calls", 0) + 1
        pr["last"] = name
        self.rig.op, self.rig.layer = name, 0
        self.status["calls_total"] += 1
        pr.setdefault("trail", []).append(name)
        pr["trail"] = pr["trail"][-40:]

    def _on_batch(self, b):
        self.status["clocks_total"] += b["clocks"]
        self.status["pins"] = {"op": b["op"], "stim": b["stim"], "uo": b["uo"], "n": self.status["calls_total"]}
        self.status["rig"] = self.rig.state()

    def _on_layer(self, name, layer, f):
        if self.layers is not None and name == "ntt" and len(self.layers) < 7:
            self.layers.append(f)

    def log(self, who, msg, kind="info"):
        self.status["log"].append({"t": time.strftime("%H:%M:%S"), "who": who, "msg": msg, "kind": kind})
        self.status["log"] = self.status["log"][-80:]

    def publish(self, section, payload):
        self.data[section] = payload
        self.status["ver"][section] += 1

    def backend(self):
        return MaskedBackend(self.chip) if self.masked else self.chip

    # ---------------- actions ----------------
    def polymul(self, args):
        rng = random.Random(args.get("seed") or random.SystemRandom().randrange(1 << 30))
        f = [rng.randrange(Q) for _ in range(256)]
        g = [rng.randrange(Q) for _ in range(256)]
        be = self.chip
        steps = []
        self.layers = []

        def step(name, fn):
            self.status["progress"]["op"] = name
            c0 = self.status["clocks_total"]
            t = time.perf_counter()
            r = fn()
            steps.append({"name": name, "wall_s": time.perf_counter() - t, "fpga_clocks": self.status["clocks_total"] - c0})
            return r
        F = step("forward NTT of f", lambda: be.ntt(f))
        layers_f = self.layers
        self.layers = None
        G_ = step("forward NTT of g", lambda: be.ntt(g))
        H = step("basemul", lambda: be.basemul(F, G_))
        h = step("inverse NTT", lambda: be.invntt(H))
        out = step("scale", lambda: be.scale(h))
        t = time.perf_counter()
        ref = polymul_schoolbook(f, g)
        cpu_s = time.perf_counter() - t
        match = sum(a == b for a, b in zip(out, ref))
        for s_, clk in zip(steps, (PM.CLOCKS_PER_CALL["ntt"], PM.CLOCKS_PER_CALL["ntt"], PM.CLOCKS_PER_CALL["basemul"],
                                   PM.CLOCKS_PER_CALL["invntt"], PM.CLOCKS_PER_CALL["scale"])):
            s_["silicon_us"] = clk / PM.f_chip()[0] * 1e6
        self.publish("polymul", {"f": f, "g": g, "F": F, "G": G_, "H": H, "out": out, "ref": ref, "match": match,
                                 "layers": [f] + layers_f, "steps": steps, "cpu_s": cpu_s})
        self.log("chip", f"multiplied two random polynomials: {match}/256 coefficients match the CPU's schoolbook result",
                 "ok" if match == 256 else "bad")

    def _measure(self, op, fn, py_fn):
        self.chip.reset_counters()
        self.chip.on_call = self._on_call
        self.status["progress"] = {"op": op, "calls": 0, "t0": time.time()}
        t0 = time.perf_counter()
        result = fn()
        wall = time.perf_counter() - t0
        calls, chip_s = dict(self.chip.calls), self.chip.chip_s
        t0 = time.perf_counter()
        py_fn(KEM())
        py_s = time.perf_counter() - t0
        tb = TimingBackend(ReferenceBackend())
        py_fn(KEM(tb))
        pr = PM.predict(op, py_s, wall - chip_s, chip_s, calls, ps=PS)
        cp = PM.chip_part(calls, tb.seconds, chip_s)
        perf = self.data["perf"].get("ops", {})
        perf[op] = {"measured_s": wall, "chip_s": chip_s, "host_s": wall - chip_s, "python_s": py_s, "calls": calls,
                    "pred": pr["predicted"], "coef": pr["coefficients"], "f_chip_mhz": pr["f_chip_hz"] / 1e6,
                    "masked": self.masked, "chip_part": {k: v for k, v in cp.items() if k.endswith("_s")}}
        self.publish("perf", {"ops": perf, "assumptions": [[k, v, s] for k, v, s in PM.assumptions()]})
        try:
            import perf
            perf.PS = PS
            perf.append({"source": "showcase", "kind": "measured", "backend": self.source_label(), "op": op,
                         "wall_s": wall, "chip_s": chip_s, "host_s": wall - chip_s, "chip_calls": calls, "masked": self.masked})
        except Exception:
            pass
        return result, calls, wall

    def source_label(self):
        return "chip model (PC)" if self.source == "simulation" else "chip on FPGA (PC + Tang Nano)"

    def keygen(self, _):
        rng = random.SystemRandom()
        d, z = rng.randbytes(32), rng.randbytes(32)
        kem = KEM(self.backend())
        (ek, dk), calls, wall = self._measure("keygen", lambda: kem.keygen_internal(d, z), lambda k: k.keygen_internal(d, z))
        p = KEM()
        rho, sigma = G(d + bytes([p.k]))
        A = p._matrix(rho)
        s = [sample_poly_cbd(PRF(p.eta1, sigma, i), p.eta1) for i in range(p.k)]
        e = [sample_poly_cbd(PRF(p.eta1, sigma, p.k + i), p.eta1) for i in range(p.k)]
        t_hat = [byte_decode(ek[384 * i:384 * (i + 1)], 12) for i in range(p.k)]
        s_hat = [byte_decode(dk[384 * i:384 * (i + 1)], 12) for i in range(p.k)]
        self.kex = {"d": d, "z": z, "ek": ek, "dk": dk}
        self.publish("kex", {"stage": "keygen", "d": d.hex(), "z": z.hex(), "rho": rho.hex(), "sigma": sigma.hex(),
                             "A": A, "s": [centered(x) for x in s], "e": [centered(x) for x in e], "s_hat": s_hat,
                             "t_hat": t_hat, "ek": ek.hex(), "dk_len": len(dk), "dk_head": dk[:48].hex(),
                             "h_ek": hashlib.sha3_256(ek).hexdigest(), "keygen": {"calls": calls, "wall_s": wall}})
        self._snoop(s[0])
        self.log("Alice", f"generated her key pair: {len(ek)}-byte public key, {len(dk)}-byte private key "
                 f"({sum(calls.values())} chip calls)")

    def encaps(self, _):
        if "ek" not in self.kex:
            raise ValueError("Alice needs a key pair first")
        ek, m = self.kex["ek"], random.SystemRandom().randbytes(32)
        kem = KEM(self.backend())
        (K, c), calls, wall = self._measure("encaps", lambda: kem.encaps_internal(ek, m), lambda k: k.encaps_internal(ek, m))
        self.kex.update({"m": m, "K_bob": K, "c": c})
        d = dict(self.data["kex"], stage="encaps", m=m.hex(), K_bob=K.hex(), c=c.hex(), K_alice=None,
                 encaps={"calls": calls, "wall_s": wall})
        self.publish("kex", d)
        self.log("Bob", f"encapsulated: shared key {K.hex()[:16]}…, {len(c)}-byte ciphertext to Alice")

    def decaps(self, _):
        if "c" not in self.kex:
            raise ValueError("Bob has not sent a ciphertext yet")
        dk, c = self.kex["dk"], self.kex["c"]
        kem = KEM(self.backend())
        K, calls, wall = self._measure("decaps", lambda: kem.decaps(dk, c), lambda k: k.decaps(dk, c))
        self.kex["K_alice"] = K
        same = K == self.kex["K_bob"]
        std = (self.kex["ek"], dk) == KEM().keygen_internal(self.kex["d"], self.kex["z"])
        d = dict(self.data["kex"], stage="decaps", K_alice=K.hex(), match=same, standard=std,
                 decaps={"calls": calls, "wall_s": wall})
        self.publish("kex", d)
        self.log("Alice", "decapsulated: shared key " + ("MATCHES Bob's" if same else "DIFFERS from Bob's"),
                 "ok" if same else "bad")

    def exchange(self, args):
        self.keygen(args)
        self.encaps(args)
        self.decaps(args)

    def send(self, args):
        if "K_alice" not in self.kex:
            raise ValueError("exchange keys first")
        msg = (args.get("msg") or "hello").encode()[:300]
        blob = seal(self.kex["K_bob"], msg)
        self._deliver(msg, blob, tampered=False)

    def _deliver(self, msg, blob, tampered, flip=None):
        try:
            got = open_(self.kex["K_alice"], blob).decode(errors="replace")
            ok = True
        except ValueError as e:
            got, ok = str(e), False
        self.publish("packet", {"plain": msg.decode(errors="replace"), "blob": blob.hex(), "nonce": blob[:16].hex(),
                                "ct": blob[16:-32].hex(), "tag": blob[-32:].hex(), "ok": ok, "received": got,
                                "tampered": tampered, "flip": flip})
        self.log("Alice", f"received {len(blob)} bytes: " + (f"“{got}”" if ok else f"REJECTED ({got})"),
                 "ok" if ok else "bad")

    def tamper_packet(self, _):
        p = self.data["packet"]
        if not p:
            raise ValueError("send a message first")
        blob = bytes.fromhex(p["blob"])
        i = 16 + random.randrange(max(1, len(blob) - 48))
        bad = blob[:i] + bytes([blob[i] ^ 0x01]) + blob[i + 1:]
        self.log("Eve", f"flipped one bit of the packet in transit (byte {i})", "eve")
        self._deliver(p["plain"].encode(), bad, tampered=True, flip=i)

    def tamper_ct(self, _):
        if "c" not in self.kex:
            raise ValueError("exchange keys first")
        good = self.kex["c"]
        self.kex["c"] = bytes([good[0] ^ 0x01]) + good[1:]
        self.log("Eve", "flipped one bit of Bob's ciphertext in transit", "eve")
        self.decaps({})
        self.log("Alice", "implicit rejection: her key is now random, Eve learns nothing", "info")
        self.kex["c"] = good

    def _snoop(self, s0):
        first = next((w for name, w in self.chip.bus if name == "ntt"), [])
        f = [0] * 256
        for j in range(128):
            f[j + 128], f[j] = first[2 * j], first[2 * j + 1]
        eta = KEM().eta1
        guess = [x if (x <= eta or x >= Q - eta) else None for x in f]
        rec = sum(g == s for g, s in zip(guess, s0))
        bins = [0] * 33
        for x in centered(f):
            bins[min(32, (x + 1664) * 33 // 3329)] += 1
        self.publish("eve", {"recovered": rec, "masked": self.masked, "bins": bins, "seen": centered(f)[:32],
                             "secret": centered(s0)[:32], "guess": [None if g is None else (g - Q if g > Q // 2 else g)
                                                                    for g in guess[:32]]})
        self.log("Eve", (f"probed the chip pins during keygen: random shares only, {rec}/256 right (chance)" if self.masked
                         else f"probed the chip pins during keygen: recovered {rec}/256 coefficients of Alice's secret!"),
                 "eve" if self.masked else "bad")

    def mask(self, args):
        self.masked = bool(args.get("on"))
        self.status["masked"] = self.masked
        self.log("Alice", "masking " + ("ON: every chip operand is split into 2 random shares" if self.masked else "OFF"))

    def timing(self, _):
        rows = []
        for i in range(3):
            d, z = random.SystemRandom().randbytes(32), random.SystemRandom().randbytes(32)
            self.chip.reset_counters()
            self.chip.on_call = self._on_call
            self.status["progress"] = {"op": f"timing run {i + 1}/3", "calls": 0}
            KEM(self.backend()).keygen_internal(d, z)
            calls = dict(self.chip.calls)
            rows.append({"secret": d.hex()[:16], "calls": sum(calls.values()),
                         "clocks": sum(n * PM.CLOCKS_PER_CALL[k] for k, n in calls.items())})
        eve = dict(self.data["eve"], timing=rows)
        self.publish("eve", eve)
        same = len({(r["calls"], r["clocks"]) for r in rows}) == 1
        self.log("Eve", "timed 3 key generations with different secrets: " +
                 ("identical clock counts, nothing to learn" if same else "DIFFERENT"), "eve" if same else "bad")

    ACTIONS = {"polymul": polymul, "keygen": keygen, "encaps": encaps, "decaps": decaps, "exchange": exchange,
               "send": send, "tamper_packet": tamper_packet, "tamper_ct": tamper_ct, "mask": mask, "timing": timing}

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
                self.status["progress"] = {}
        threading.Thread(target=work, daemon=True).start()
        return True


def make_handler(app):
    def page():
        return open(os.path.join(HERE, "showcase.html"), "rb").read()

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
                html = page().replace(b"</head>", f"<script>window.__INIT = {init};</script></head>".encode(), 1)
                self._send(html, "text/html; charset=utf-8")
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
            if action not in Showcase.ACTIONS:
                return self.send_error(404)
            n = int(self.headers.get("Content-Length", 0) or 0)
            args = json.loads(self.rfile.read(n) or b"{}") if n else {}
            self._send(json.dumps({"started": app.run(action, args)}).encode(), "application/json")
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="Python chip model instead of the board")
    ap.add_argument("--port", help="serial port of the Tang Nano")
    ap.add_argument("--baud", type=int, default=1000000)
    ap.add_argument("--http", type=int, default=8080)
    a = ap.parse_args()
    if a.sim:
        emu, source = SimEmu(), "simulation"
    else:
        from tt_emu import TTEmu
        emu = TTEmu(a.port, a.baud)
        emu.ping()
        source = f"Tang Nano FPGA on {emu.port}"
    app = Showcase(emu, source, a.baud)
    app.log("demo", f"chip: {source}")
    srv = ThreadingHTTPServer(("127.0.0.1", a.http), make_handler(app))
    print(f"showcase ({source}) at http://localhost:{a.http}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
