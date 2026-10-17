"""Design A (team Spec 1-5): cycle-accurate pin-level model of the butterfly-stream coprocessor.

    chip = ChipA()
    uo_out = chip.step(ui_in, uio_in)     # once per clock

Arithmetic: model/chip_arith.py (K-RED, scaled ROM). Timing: sim/protocol.py. The model is behavioural
inside: when a unit's last input arrives it computes the pair and schedules the 3 bytes at the fixed
offsets. The RTL in src/ must produce the same uo_out on every clock.

Job rules (Spec 3): valid+sof starts a job and is its first input; op is latched on that clock; the job
ends by itself after JOB_INPUTS inputs; extra inputs and valid words outside a job are ignored; every
sof flushes, cancelling whatever is still in flight (uo_out = 0 from 2 clocks after the sof pin clock),
so a host must not start a job before the previous job's last byte.
"""
import chip_arith as C
from mlkem_ntt_model import a_zidx_fwd, a_zidx_inv
from pins import PinIn
from protocol import JOB_INPUTS, LAT, OFFSETS, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE, PERIOD, pack_pair


class ProtocolError(Exception):
    """The host broke the pin protocol; real silicon would produce garbage here."""


class StreamEngine:
    def __init__(self):
        self.cycle = 0
        self.sched = {}             # cycle -> output byte
        self.out_valid = False      # debug: this cycle carried a result byte
        self.job_op = None          # None = idle
        self.reset_job()

    def reset_job(self):
        self.n_in = 0               # inputs taken in this job
        self.unit = []              # inputs of the unit being received
        self.t0 = None              # pin cycle of the unit's first input
        self.next_ok = -1           # earliest start of the next unit
        self.layer = self.bf = self.piece = 0
        self.last_pv = -1           # cycle of the last scheduled pair_valid

    # ---- job control ----
    def start_job(self, t, op):
        # every sof flushes (Spec 3 "a new start of frame always wins"): bytes from 2 clocks after the
        # sof pin clock on are dropped, and so is everything still in flight
        for c in [c for c in self.sched if c >= t + 2]:
            del self.sched[c]
        self.job_op = op
        self.reset_job()

    def take(self, t, din):
        """One valid input word of the running job (pin cycle t)."""
        op = self.job_op
        if op is None or self.n_in >= JOB_INPUTS[op]:
            return                                           # outside a job: ignored
        offs = OFFSETS[op]
        if not self.unit:
            if t < self.next_ok:
                raise ProtocolError(f"cycle {t}: unit starts before cycle {self.next_ok}")
            self.t0 = t
        elif t != self.t0 + offs[len(self.unit)]:
            raise ProtocolError(f"cycle {t}: input {len(self.unit)} of a unit must be at offset {offs[len(self.unit)]}")
        self.unit.append(din)
        self.n_in += 1
        if len(self.unit) == len(offs):
            pair = self.compute(op, self.unit)
            first = self.t0 + LAT[op]
            for i, b in enumerate(pack_pair(*pair)):
                if first + i in self.sched:
                    raise ProtocolError(f"output collision at cycle {first + i}")
                self.sched[first + i] = b
            self.last_pv = first - 1
            self.next_ok = self.t0 + PERIOD[op]
            self.unit = []

    def check_unit_gap(self, t):
        """An idle clock inside a unit is only allowed between the spec'd offsets."""
        if self.unit and t - self.t0 >= OFFSETS[self.job_op][len(self.unit)]:
            raise ProtocolError(f"cycle {t}: missing input {len(self.unit)} of a unit")

    def compute(self, op, w):
        if op in (OP_CT, OP_GS):
            b, a = w
            if op == OP_CT:
                out = C.ct(a, b, a_zidx_fwd(self.layer, self.bf))
            else:
                out = C.gs(a, b, a_zidx_inv(self.layer, self.bf))
            self.bf = (self.bf + 1) & 127
            if self.bf == 0:
                self.layer += 1
            return out
        if op == OP_SCALE:
            return C.scale(w[0]), C.scale(w[1])
        g1, f1, g0, f0 = w
        out = C.basemul_piece(f0, f1, g0, g1, self.piece)
        self.piece += 1
        return out

    def output(self):
        self.out_valid = self.cycle in self.sched
        return self.sched.pop(self.cycle, 0)


class ChipA(StreamEngine):
    def step(self, ui_in, uio_in):
        p = PinIn.decode(ui_in, uio_in)
        t = self.cycle
        out = self.output()
        if p.valid and p.sof:
            self.start_job(t, p.op)
            self.take(t, p.din)
        elif p.valid:
            self.take(t, p.din)
        elif self.job_op is not None:
            self.check_unit_gap(t)
        self.cycle += 1
        return out
