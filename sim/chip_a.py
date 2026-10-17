"""Design A: cycle-accurate pin-level model of the butterfly-stream coprocessor.

    chip = ChipA(mult="serial")
    uo_out = chip.step(ui_in, uio_in)     # once per clock

Arithmetic comes from the golden model (model/mlkem_ntt_model.py); timing from sim/protocol.py.
The model is behavioural inside: when a transaction's last word arrives it computes the result
and schedules the 3 output bytes at the fixed protocol offsets. The RTL must produce the same
uo_out on every clock.
"""
from mlkem_ntt_model import Q, ZETAS, a_zidx_fwd, a_zidx_inv, basemul_gamma, ct_butterfly, gs_butterfly, modmul
from pins import PinIn
from protocol import LAT, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE, PERIOD, WORDS, pack_pair


class ProtocolError(Exception):
    """The host broke the pin protocol; real silicon would produce garbage here."""


class StreamEngine:
    """Shared by design A and design B's stream mode: counters, PE timing, output schedule."""

    def __init__(self, mult="serial"):
        assert mult in ("serial", "parallel")
        self.mult = mult
        self.cycle = 0
        self.sched = {}             # cycle -> output byte
        self.next_ok = 0            # earliest cycle a new transaction may start
        self.reset_counters()
        self.frame_op = None
        self.cur = []               # words of the transaction being received
        self.t0 = None
        self.out_valid = False      # debug: did this cycle carry a result byte?

    def reset_counters(self):
        self.layer = 0              # 0..6
        self.bf = 0                 # butterfly within layer, 0..127
        self.pair = 0               # basemul pair, 0..127

    def emit(self, t, values):
        for i, b in enumerate(pack_pair(*values)):
            if t + i in self.sched:
                raise ProtocolError(f"output collision at cycle {t + i}")
            self.sched[t + i] = b

    def stream_word(self, t, din, op):
        if op != self.frame_op:
            raise ProtocolError(f"cycle {t}: op changed inside a frame without sof")
        if not self.cur:
            if t < self.next_ok:
                raise ProtocolError(f"cycle {t}: transaction starts before cycle {self.next_ok}")
            self.t0 = t
        elif t != self.t0 + len(self.cur):
            raise ProtocolError(f"cycle {t}: gap inside a transaction")
        self.cur.append(din)
        if len(self.cur) == WORDS[op]:
            self.emit(self.t0 + LAT[self.mult][op], self.compute(op, self.cur))
            self.next_ok = self.t0 + PERIOD[self.mult][op]
            self.cur = []

    def compute(self, op, w):
        if op in (OP_CT, OP_GS):
            if self.layer > 6:
                raise ProtocolError("more than 896 butterflies without sof")
            if op == OP_CT:
                out = ct_butterfly(w[0], w[1], ZETAS[a_zidx_fwd(self.layer, self.bf)])
            else:
                out = gs_butterfly(w[0], w[1], ZETAS[a_zidx_inv(self.layer, self.bf)])
            self.bf = (self.bf + 1) & 127
            if self.bf == 0:
                self.layer += 1
            return out
        if op == OP_SCALE:
            return modmul(w[0], 3303), modmul(w[1], 3303)
        a0, a1, b0, b1 = w                                 # basemul
        g = basemul_gamma(self.pair)
        self.pair = (self.pair + 1) & 127
        return (modmul(a0, b0) + modmul(modmul(a1, b1), g)) % Q, (modmul(a0, b1) + modmul(a1, b0)) % Q

    def check_idle(self, t):
        if self.cur:
            raise ProtocolError(f"cycle {t}: gap inside a transaction")

    def output(self):
        """uo_out for the current cycle (before this cycle's edge)."""
        self.out_valid = self.cycle in self.sched
        return self.sched.pop(self.cycle, 0)


class ChipA(StreamEngine):
    def step(self, ui_in, uio_in):
        p = PinIn.decode(ui_in, uio_in)
        t = self.cycle
        out = self.output()
        if p.sof and not p.valid:
            raise ProtocolError(f"cycle {t}: sof without valid")
        if p.valid:
            if p.sof:
                if self.cur:
                    raise ProtocolError(f"cycle {t}: sof inside a transaction")
                self.reset_counters()
                self.frame_op = p.op
            self.stream_word(t, p.din, p.op)
        else:
            self.check_idle(t)
        self.cycle += 1
        return out
