"""Interactive live demo: ML-KEM (default ML-KEM-512) key exchange and encrypted packets through our NTT chip, with Eve.

    python host/live_demo.py            # chip on the Tang Nano (auto-detected)
    python host/live_demo.py --sim      # Python chip model, no board needed
    then open http://localhost:8080

Alice and Bob both use the one chip on the board (on the TT demo board each would have their own).
Every NTT / basemul / scale runs on the chip; hashing and encoding run on the PC (the RP2350's job).

Eve can
  * snoop the chip's input pins while Alice generates her key: without masking the secret
    polynomial crosses the pins in the clear in the first NTT layer; with host-side masking she only
    sees uniformly random shares,
  * tamper with the ciphertext or the packet: ML-KEM's implicit rejection / the MAC catch it,
  * eavesdrop: everything on the network is public and useless without Alice's secret key.
"""
import argparse
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
from mlkem import G, PARAMS, PRF, ReferenceBackend, TimingBackend, sample_poly_cbd  # noqa: E402

PS = "ML-KEM-512"           # parameter set (our target); --ps ML-KEM-768 to change


def KEM(backend=None):
    return PARAMS[PS](backend)
from packet import open_, seal  # noqa: E402

Q = 3329


class Session:
    def __init__(self, emu, source):
        self.lock = threading.Lock()
        self.chip = BoardBackend(emu)
        self.source = source
        self.masked = False
        self.state = {"source": source, "masked": False, "busy": None, "progress": {}, "log": [],
                      "alice": {}, "bob": {}, "wire": {}, "eve": {}, "perf": {}, "timing": None}
        self.ek = self.dk = self.c = self.K_bob = self.K_alice = self.d = None
        self.chip.on_call = self._on_call

    # ---- helpers
    def backend(self):
        return MaskedBackend(self.chip) if self.masked else self.chip

    def _on_call(self, name):
        pr = self.state["progress"]
        pr["calls"] = pr.get("calls", 0) + 1
        pr["last"] = name

    def log(self, who, msg, kind="info"):
        self.state["log"].append({"t": time.strftime("%H:%M:%S"), "who": who, "msg": msg, "kind": kind})
        self.state["log"] = self.state["log"][-60:]

    def _measure(self, op, fn, py_fn):
        """Run fn on the chip and py_fn pure-Python; record measurements, coefficients, predictions."""
        self.chip.reset_counters()
        self.chip.on_call = self._on_call
        self.state["progress"] = {"op": op, "calls": 0, "t0": time.time()}
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
        self.state["perf"][op] = {"measured_s": wall, "chip_s": chip_s, "host_s": wall - chip_s, "python_s": py_s,
                                  "calls": calls, "pred": pr["predicted"], "coef": pr["coefficients"],
                                  "f_chip_mhz": pr["f_chip_hz"] / 1e6, "masked": self.masked,
                                  "chip_part": {k: v for k, v in cp.items() if k.endswith("_s")}}
        try:
            import perf
            perf.append({"source": "live demo", "kind": "measured", "backend": self.source_label(), "op": op,
                         "wall_s": wall, "chip_s": chip_s, "host_s": wall - chip_s, "chip_calls": calls,
                         "masked": self.masked})
        except Exception:
            pass
        return result

    def source_label(self):
        return "chip on FPGA (PC + Tang Nano)" if self.source != "simulation" else "chip model (PC)"

    # ---- actions
    def keygen(self, _):
        rng = random.SystemRandom()
        self.d, z = rng.randbytes(32), rng.randbytes(32)
        kem = KEM(self.backend())
        d = self.d
        self.ek, self.dk = self._measure("keygen", lambda: kem.keygen_internal(d, z),
                                         lambda k: k.keygen_internal(d, z))
        self.c = self.K_bob = self.K_alice = None
        self.state["alice"] = {"ek": self.ek.hex(), "ek_len": len(self.ek), "dk_len": len(self.dk), "key": None}
        self.state["bob"] = {}
        self.state["wire"] = {"ek": self.ek.hex()[:96]}
        self.log("Alice", f"generated a key pair on the chip ({sum(self.state['perf']['keygen']['calls'].values())} chip calls); "
                 f"public key {len(self.ek)} B sent to Bob")
        self._snoop()

    def encaps(self, _):
        if not self.ek:
            raise ValueError("Alice needs a key pair first")
        kem, m = KEM(self.backend()), random.SystemRandom().randbytes(32)
        ek = self.ek
        self.K_bob, self.c = self._measure("encaps", lambda: kem.encaps_internal(ek, m),
                                           lambda k: k.encaps_internal(ek, m))
        self.state["bob"] = {"key": self.K_bob.hex()}
        self.state["wire"]["ct"] = self.c.hex()[:96]
        self.state["wire"]["ct_len"] = len(self.c)
        self.log("Bob", f"encapsulated a fresh shared key; ciphertext {len(self.c)} B sent to Alice")

    def decaps(self, _):
        if not self.c:
            raise ValueError("Bob has not sent a ciphertext yet")
        kem, dk, c = KEM(self.backend()), self.dk, self.c
        self.K_alice = self._measure("decaps", lambda: kem.decaps(dk, c), lambda k: k.decaps(dk, c))
        self.state["alice"]["key"] = self.K_alice.hex()
        same = self.K_alice == self.K_bob
        self.log("Alice", "decapsulated: shared key " + ("MATCHES Bob's" if same else "DIFFERS from Bob's"),
                 "ok" if same else "bad")

    def exchange(self, args):
        self.keygen(args)
        self.encaps(args)
        self.decaps(args)

    def send(self, args):
        if not (self.K_bob and self.K_alice):
            raise ValueError("exchange keys first")
        msg = (args.get("msg") or "hello from Bob").encode()[:400]
        blob = seal(self.K_bob, msg)
        self.state["wire"]["packet"] = blob.hex()
        self._deliver(blob, "Bob")

    def _deliver(self, blob, sender):
        try:
            text = open_(self.K_alice, blob).decode(errors="replace")
            self.state["alice"]["inbox"] = text
            self.log("Alice", f"received {len(blob)} B packet from {sender}, authenticated and decrypted: “{text}”", "ok")
        except ValueError as e:
            self.state["alice"]["inbox"] = None
            self.log("Alice", f"packet REJECTED: {e}", "bad")

    def tamper_packet(self, _):
        blob = bytes.fromhex(self.state["wire"].get("packet", ""))
        if not blob:
            raise ValueError("send a packet first")
        i = 16 + random.randrange(len(blob) - 48)
        bad = blob[:i] + bytes([blob[i] ^ 0x01]) + blob[i + 1:]
        self.log("Eve", f"flipped one bit (byte {i}) of the packet in transit", "eve")
        self._deliver(bad, "Bob (tampered by Eve)")

    def tamper_ct(self, _):
        if not self.c:
            raise ValueError("Bob has not sent a ciphertext yet")
        good = self.c
        self.c = bytes([good[0] ^ 0x01]) + good[1:]
        self.log("Eve", "flipped one bit of Bob's ML-KEM ciphertext in transit", "eve")
        self.decaps({})
        self.log("Alice", "implicit rejection: her key is now unrelated to Bob's, so Eve learns nothing", "info")
        self.c = good

    def eavesdrop(self, _):
        blob = bytes.fromhex(self.state["wire"].get("packet", ""))
        if not blob:
            raise ValueError("send a packet first")
        import hashlib
        guess = hashlib.sha3_256(self.ek + self.c).digest()        # anything built from public data only
        try:
            open_(guess, blob)
            self.log("Eve", "decrypted the packet?!", "bad")
        except ValueError:
            self.log("Eve", "has the public key, the ciphertext and the packet, but no key that opens it", "eve")

    def _snoop(self):
        """Eve's probe on the chip's input pins during the first NTT of Alice's keygen (NTT of s[0])."""
        first = next((w for name, w in self.chip.bus if name == "ntt"), [])
        f = [0] * 256
        for j in range(128):                                     # layer 0 sends b = f[j+128], a = f[j]
            f[j + 128], f[j] = first[2 * j], first[2 * j + 1]
        p = KEM()
        rho, sigma = G(self.d + bytes([p.k]))
        s0 = sample_poly_cbd(PRF(p.eta1, sigma, 0), p.eta1)     # Alice's real secret polynomial
        guess = [x if (x <= p.eta1 or x >= Q - p.eta1) else None for x in f]   # secret coeffs are in -eta1..eta1
        recovered = sum(g == s for g, s in zip(guess, s0))
        centered = [x - Q if x > Q // 2 else x for x in f]
        bins = [0] * 33
        for x in centered:
            bins[min(32, (x + 1664) * 33 // 3329)] += 1
        self.state["eve"] = {"recovered": recovered, "masked": self.masked, "bins": bins,
                             "sample": f[:24], "secret_sample": [x - Q if x > Q // 2 else x for x in s0[:24]]}
        if self.masked:
            self.log("Eve", f"probed the chip pins during keygen: uniformly random shares, {recovered}/256 secret coefficients right (chance)", "eve")
        else:
            self.log("Eve", f"probed the chip pins during keygen: recovered {recovered}/256 coefficients of Alice's secret key!", "bad")

    def set_mask(self, args):
        self.masked = bool(args.get("on"))
        self.state["masked"] = self.masked
        self.log("Alice", "host-side masking " + ("ON: every chip operand is split into two random shares (2x chip calls)"
                                                  if self.masked else "OFF"))

    def timing(self, _):
        rows = []
        for i in range(3):
            d, z = random.SystemRandom().randbytes(32), random.SystemRandom().randbytes(32)
            self.chip.reset_counters()
            self.chip.on_call = self._on_call
            self.state["progress"] = {"op": f"timing run {i + 1}/3", "calls": 0, "t0": time.time()}
            KEM(self.backend()).keygen_internal(d, z)
            calls = dict(self.chip.calls)
            clocks = sum(n * PM.CLOCKS_PER_CALL[k] for k, n in calls.items())
            rows.append({"key": d.hex()[:12], "calls": sum(calls.values()), "clocks": clocks})
        self.state["timing"] = rows
        same = len({(r["calls"], r["clocks"]) for r in rows}) == 1
        self.log("Eve", "timed 3 key generations with different secrets: chip clocks " +
                 ("identical, nothing to learn" if same else "DIFFER"), "eve" if same else "bad")

    ACTIONS = {"exchange": exchange, "keygen": keygen, "encaps": encaps, "decaps": decaps, "send": send,
               "tamper_packet": tamper_packet, "tamper_ct": tamper_ct, "eavesdrop": eavesdrop, "mask": set_mask,
               "timing": timing}

    def run(self, action, args):
        if self.state["busy"]:
            return False
        self.state["busy"] = action

        def work():
            try:
                with self.lock:
                    self.ACTIONS[action](self, args)
            except Exception as e:                                # show it, keep serving
                self.log("demo", f"{action}: {e}", "bad")
            finally:
                self.state["busy"] = None
                self.state["progress"] = {}
        threading.Thread(target=work, daemon=True).start()
        return True


def make_handler(session):
    page = open(os.path.join(HERE, "live_demo.html"), "rb").read()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/?"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            elif self.path == "/api/state":
                st = dict(session.state, ps=PS)
                if st.get("progress", {}).get("t0"):
                    st["progress"] = dict(st["progress"], elapsed=time.time() - st["progress"]["t0"])
                st["assumptions"] = [[k, v, s] for k, v, s in PM.assumptions()]
                self._json(st)
            else:
                self.send_error(404)

        def do_POST(self):
            if not self.path.startswith("/api/"):
                return self.send_error(404)
            action = self.path[5:]
            if action not in Session.ACTIONS:
                return self.send_error(404)
            n = int(self.headers.get("Content-Length", 0) or 0)
            args = json.loads(self.rfile.read(n) or b"{}") if n else {}
            self._json({"started": session.run(action, args)})
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="Python chip model instead of the board")
    ap.add_argument("--port", help="serial port of the Tang Nano")
    ap.add_argument("--baud", type=int, default=1000000)
    ap.add_argument("--http", type=int, default=8080)
    ap.add_argument("--ps", default="ML-KEM-512", choices=["ML-KEM-512", "ML-KEM-768"], help="parameter set")
    a = ap.parse_args()
    global PS
    PS = a.ps
    if a.sim:
        emu, source = SimEmu(), "simulation"
    else:
        from tt_emu import TTEmu
        emu = TTEmu(a.port, a.baud)
        emu.ping()
        source = f"Tang Nano on {emu.port}"
    session = Session(emu, source)
    session.log("demo", f"chip: {source}. Press 'Exchange keys' to start.")
    srv = ThreadingHTTPServer(("127.0.0.1", a.http), make_handler(session))
    print(f"live demo ({source}) at http://localhost:{a.http}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
