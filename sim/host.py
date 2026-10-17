"""RP2350 host model: turns ntt / invntt / basemul / scale calls into per-clock pin stimulus,
runs it through a chip model in lockstep, samples uo_out at the fixed protocol offsets and
decodes ByteEncode12.

A Host is an ML-KEM backend:  MLKEM768(backend=Host(ChipA()))

Each transaction's input words are built at the clock they are sent, from coefficients the host
has already received back. If a coefficient is still in flight the host idles (counted as a stall),
like a real in-order host would.
"""
import random
from dataclasses import dataclass, field

from chip_a import ChipA
from chip_b import ChipB
from mlkem_ntt_model import N
from pins import IDLE, PinIn
from protocol import (LAT, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE, PERIOD, block_lat, block_period,
                      header, unpack_pair)

INF = float("inf")


@dataclass
class Job:
    words: list                 # list of PinIn builders: each is a function(data) -> PinIn
    needs: list                 # data indices that must be back before the first word goes out
    outs: list                  # data indices the result pairs are written to, in output order
    lat: int = 0                # first word -> first result byte
    period: int = 1             # first word -> earliest next job
    out_stride: int = 3         # clocks between result pairs


@dataclass
class CallStats:
    op: str
    clocks: int
    stalls: int
    words_in: int
    bytes_out: int


@dataclass
class Trace:
    """Per-clock stimulus and expected outputs, for export to cocotb / the Tang Nano player."""
    stim: list = field(default_factory=list)       # 16-bit words {uio_in, ui_in}
    expect: list = field(default_factory=list)     # uo_out
    out_valid: list = field(default_factory=list)  # debug: chip produced a result byte this clock
    marks: list = field(default_factory=list)      # (cycle, label)


class Host:
    def __init__(self, chip, shuffle=False, record=False, seed=None):
        self.chip = chip
        self.design = "B" if isinstance(chip, ChipB) else "A"
        self.mult = chip.mult
        self.shuffle = shuffle      # B: chip LFSR shuffle bit; A: host reorders butterflies sharing a twiddle
        self.rng = random.Random(seed)   # stands in for the RP2350 TRNG
        self.stats = []
        self.trace = Trace() if record else None
        self.last_out = -1          # last cycle with a scheduled result byte (avoid collisions)

    # ---------------- generic lockstep engine ----------------
    def _run(self, label, jobs, data):
        chip = self.chip
        ready = {}                  # data index -> first cycle it may be read (absent = ready)
        expect = {}                 # cycle -> (job, pair index, byte index)
        got = {}
        t_start = chip.cycle
        next_ok = chip.cycle
        stalls = words_in = bytes_out = 0
        ji = 0
        sending = []                # remaining PinIns of the job being sent
        if self.trace is not None:
            self.trace.marks.append((len(self.trace.stim), label))

        while ji < len(jobs) or sending or expect:
            t = chip.cycle
            pin = IDLE
            if sending:
                pin = sending.pop(0)
            elif ji < len(jobs):
                job = jobs[ji]
                t_out = t + job.lat
                if t >= next_ok and t_out > self.last_out and all(ready.get(i, 0) <= t for i in job.needs):
                    words = [w(data) for w in job.words]
                    pin, sending = words[0], words[1:]
                    words_in += len(words)
                    for p, idx in enumerate(job.outs):
                        for b in range(3):
                            expect[t_out + p * job.out_stride + b] = (ji, p, b)
                        for i in idx:
                            ready[i] = INF
                    if job.outs:
                        self.last_out = t_out + (len(job.outs) - 1) * job.out_stride + 2
                    next_ok = t + job.period
                    ji += 1
                elif t >= next_ok:
                    stalls += 1

            ui, uio = pin.encode()
            uo = chip.step(ui, uio)
            if self.trace is not None:
                self.trace.stim.append((uio << 8) | ui)
                self.trace.expect.append(uo)
                self.trace.out_valid.append(chip.out_valid)

            if t in expect:
                j, p, b = expect.pop(t)
                got.setdefault((j, p), []).append(uo)
                bytes_out += 1
                if b == 2:
                    v = unpack_pair(*got.pop((j, p)))
                    for i, val in zip(jobs[j].outs[p], v):
                        data[i] = val
                        ready[i] = t + 1
        self.stats.append(CallStats(label, chip.cycle - t_start, stalls, words_in, bytes_out))

    # ---------------- job builders ----------------
    @staticmethod
    def _word(idx, sof=False, op=0):
        return lambda d: PinIn(din=d[idx], valid=True, sof=sof, op=op)

    @staticmethod
    def _const(din, sof=False, op=0):
        return lambda d: PinIn(din=din, valid=True, sof=sof, op=op)

    def _stream_jobs(self, op, groups, outs):
        """groups: input index lists per transaction; outs: [(i0, i1)] result targets per transaction."""
        jobs = []
        lat, per = LAT[self.mult][op], PERIOD[self.mult][op]
        if self.design == "B":       # B: a stream-mode header precedes the frame
            jobs.append(Job([self._const(header(False), sof=True, op=op)], [], [], 0, 1))
        for n, (g, o) in enumerate(zip(groups, outs)):
            sof = self.design == "A" and n == 0
            ws = [self._word(i, sof=(sof and k == 0), op=op) for k, i in enumerate(g)]
            jobs.append(Job(ws, list(g), [o], lat, per))
        return jobs

    def _bf_order(self, inverse):
        """Canonical FIPS 203 butterfly order: [(j, j+L)] for all 7 layers. With shuffle (design A)
        the host permutes the butterflies inside each run that shares a twiddle: the chip's counters
        only count, so any order inside such a run gets the same twiddle."""
        pairs = []
        for layer in range(7):
            L = (2 << layer) if inverse else (128 >> layer)
            for start in range(0, N, 2 * L):
                group = [(j, j + L) for j in range(start, start + L)]
                if self.shuffle:
                    self.rng.shuffle(group)
                pairs += group
        return pairs

    def _block_jobs(self, passes):
        jobs = []
        for pid in passes:
            for blk in range(16):
                idx = [blk + 16 * m for m in range(16)] if pid in (0, 3) else [16 * blk + m for m in range(16)]
                ws = [self._const(header(True, pid, blk, self.shuffle), sof=True)] + [self._word(i) for i in idx]
                outs = [(idx[2 * k], idx[2 * k + 1]) for k in range(8)]
                jobs.append(Job(ws, idx, outs, block_lat(pid, self.mult), block_period(pid, self.mult)))
        return jobs

    def _layer_gaps(self, jobs, op):
        """A with host shuffle: the next layer's first butterfly may need the previous layer's last
        result, so wait LAT clocks after every layer. A fixed gap keeps the timing independent of
        the (secret) permutation; without shuffle the canonical order never needs it."""
        if self.shuffle:
            for k in range(127, len(jobs) - 1, 128):
                jobs[k].period += LAT[self.mult][op]
        return jobs

    # ---------------- backend interface ----------------
    def ntt(self, f):
        d = list(f)
        if self.design == "A":
            pairs = self._bf_order(False)
            self._run("ntt", self._layer_gaps(self._stream_jobs(OP_CT, pairs, pairs), OP_CT), d)
        else:
            self._run("ntt", self._block_jobs((0, 1)), d)
        return d

    def invntt(self, f):
        d = list(f)
        if self.design == "A":
            pairs = self._bf_order(True)
            self._run("invntt", self._layer_gaps(self._stream_jobs(OP_GS, pairs, pairs), OP_GS), d)
        else:
            self._run("invntt", self._block_jobs((2, 3)), d)
        return d

    def scale(self, f):
        d = list(f)
        pairs = [(2 * i, 2 * i + 1) for i in range(128)]
        self._run("scale", self._stream_jobs(OP_SCALE, pairs, pairs), d)
        return d

    def basemul(self, f, g):
        d = list(f) + list(g) + [0] * N          # f at 0.., g at 256.., h at 512..
        groups = [(2 * i, 2 * i + 1, N + 2 * i, N + 2 * i + 1) for i in range(128)]
        outs = [(2 * N + 2 * i, 2 * N + 2 * i + 1) for i in range(128)]
        self._run("basemul", self._stream_jobs(OP_BASEMUL, groups, outs), d)
        return d[2 * N:]


def make_host(design, mult="serial", shuffle=False, record=False, seed=None):
    chip = ChipA(mult) if design == "A" else ChipB(mult)
    return Host(chip, shuffle=shuffle, record=record, seed=seed)
