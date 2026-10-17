"""RP2350 host model (team Spec 1 "software chip" harness): turns forward / inverse / basemul / scale calls
into per-clock pin stimulus, runs it through a chip model in lockstep, samples uo_out at the fixed
offsets of sim/protocol.py and decodes ByteEncode12.

A Host is an ML-KEM backend:  MLKEM768(backend=Host(ChipA()))
  ntt, invntt: plain results.  basemul: FACTOR * plain (K-RED).  scale: x * 3303 * FACTOR^-1.
  factor = FACTOR (2197 team chip, 169 own; model/chip_arith.py) tells model/mlkem.py about it.

Each unit's input words are built at the clock they are sent, from coefficients already received
back. If a coefficient is still in flight the host idles (counted as a stall).
"""
import random
from dataclasses import dataclass, field

from chip_a import ChipA
from chip_arith import FACTOR
from chip_b import ChipB
from mlkem_ntt_model import N
from pins import IDLE, PinIn
from protocol import (LAT, OFFSETS, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE, PERIOD, block_lat, block_period,
                      header, unpack_pair)

INF = float("inf")


@dataclass
class Unit:
    words: list                 # functions data -> PinIn
    offsets: tuple              # clock offset of each word from the unit start
    needs: list                 # data indices that must be back before the unit starts
    outs: list                  # [(i0, i1)] targets for each result pair, in output order
    lat: int = 0                # unit start -> first result byte
    period: int = 1             # unit start -> earliest next unit start
    out_stride: int = 3


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
    factor = FACTOR

    def __init__(self, chip, shuffle=False, record=False, seed=None):
        self.chip = chip
        self.design = "B" if isinstance(chip, ChipB) else "A"
        self.shuffle = shuffle      # B: chip LFSR shuffle bit; A: host reorders butterflies sharing a twiddle
        self.rng = random.Random(seed)   # stands in for the RP2350 TRNG
        self.stats = []
        self.trace = Trace() if record else None
        self.last_out = -1

    # ---------------- generic lockstep engine ----------------
    def _run(self, label, units, data):
        chip = self.chip
        ready, expect, got = {}, {}, {}
        t_start = next_ok = chip.cycle
        stalls = words_in = bytes_out = 0
        ui_ = 0
        sending = {}                # cycle -> PinIn
        if self.trace is not None:
            self.trace.marks.append((len(self.trace.stim), label))

        while ui_ < len(units) or sending or expect:
            t = chip.cycle
            pin = sending.pop(t, None)
            if pin is None and not sending and ui_ < len(units):
                u = units[ui_]
                t_out = t + u.lat
                if t >= next_ok and t_out > self.last_out and all(ready.get(i, 0) <= t for i in u.needs):
                    words = [w(data) for w in u.words]
                    for w, off in zip(words, u.offsets):
                        sending[t + off] = w
                    pin = sending.pop(t)
                    words_in += len(words)
                    for p, idx in enumerate(u.outs):
                        for b in range(3):
                            expect[t_out + p * u.out_stride + b] = (ui_, p, b)
                        for i in idx:
                            ready[i] = INF
                    if u.outs:
                        self.last_out = t_out + (len(u.outs) - 1) * u.out_stride + 2
                    next_ok = t + u.period
                    ui_ += 1
                elif t >= next_ok:
                    stalls += 1

            ui, uio = (pin or IDLE).encode()
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
                    for i, val in zip(units[j].outs[p], v):
                        if val >= 3329:
                            raise IOError(f"result {val} >= q at cycle {t}: hardware fault")
                        data[i] = val
                        ready[i] = t + 1
        self.stats.append(CallStats(label, chip.cycle - t_start, stalls, words_in, bytes_out))

    # ---------------- unit builders ----------------
    @staticmethod
    def _word(idx, sof=False, op=0):
        return lambda d: PinIn(din=d[idx], valid=True, sof=sof, op=op)

    @staticmethod
    def _const(din, sof=False, op=0):
        return lambda d: PinIn(din=din, valid=True, sof=sof, op=op)

    def _stream_units(self, op, groups, outs):
        """One chip job. groups: input indices per unit in send order; outs: (r0, r1) targets per unit."""
        units = []
        if self.design == "B":       # B: a stream-mode header starts the job
            units.append(Unit([self._const(header(False), sof=True, op=op)], (0,), [], [], 0, 1))
        for n, (g, o) in enumerate(zip(groups, outs)):
            first = self.design == "A" and n == 0
            ws = [self._word(i, sof=(first and k == 0), op=op) for k, i in enumerate(g)]
            units.append(Unit(ws, OFFSETS[op], list(g), [o], LAT[op], PERIOD[op]))
        return units

    def _bf_order(self, inverse):
        """Butterflies (j, j+len) in canonical FIPS 203 order. With shuffle (design A) the host permutes
        butterflies inside each run that shares a twiddle; the chip's counters only count."""
        pairs = []
        for layer in range(7):
            L = (2 << layer) if inverse else (128 >> layer)
            for start in range(0, N, 2 * L):
                group = [(j, j + L) for j in range(start, start + L)]
                if self.shuffle:
                    self.rng.shuffle(group)
                pairs += group
        return pairs

    def _layer_gaps(self, units, op):
        """A with host shuffle: wait LAT clocks after every layer, so the next layer never needs a result
        still in flight. A fixed gap keeps the timing independent of the (secret) permutation."""
        if self.shuffle:
            first = 1 if self.design == "B" else 0
            for k in range(first + 127, len(units) - 1, 128):
                units[k].period += LAT[op]
        return units

    def _block_units(self, passes):
        units = []
        for pid in passes:
            for blk in range(16):
                idx = [blk + 16 * m for m in range(16)] if pid in (0, 3) else [16 * blk + m for m in range(16)]
                ws = [self._const(header(True, pid, blk, self.shuffle), sof=True)] + [self._word(i) for i in idx]
                outs = [(idx[2 * k], idx[2 * k + 1]) for k in range(8)]
                units.append(Unit(ws, tuple(range(17)), idx, outs, block_lat(pid), block_period(pid)))
        return units

    def _butterflies(self, op, inverse, label, f):
        d = list(f)
        pairs = self._bf_order(inverse)
        groups = [(hi, lo) for lo, hi in pairs]          # send b = f[j+len] first, then a = f[j]
        self._run(label, self._layer_gaps(self._stream_units(op, groups, pairs), op), d)
        return d

    # ---------------- backend interface ----------------
    def ntt(self, f):
        if self.design == "B":
            d = list(f)
            self._run("ntt", self._block_units((0, 1)), d)
            return d
        return self._butterflies(OP_CT, False, "ntt", f)

    def invntt(self, f):
        if self.design == "B":
            d = list(f)
            self._run("invntt", self._block_units((2, 3)), d)
            return d
        return self._butterflies(OP_GS, True, "invntt", f)

    def scale(self, f):
        d = list(f)
        pairs = [(2 * i, 2 * i + 1) for i in range(128)]
        self._run("scale", self._stream_units(OP_SCALE, pairs, pairs), d)
        return d

    def basemul(self, f, g):
        d = list(f) + list(g) + [0] * N          # f at 0.., g at 256.., h at 512..
        groups = [(N + 2 * i + 1, 2 * i + 1, N + 2 * i, 2 * i) for i in range(128)]   # g1, f1, g0, f0
        outs = [(2 * N + 2 * i, 2 * N + 2 * i + 1) for i in range(128)]
        self._run("basemul", self._stream_units(OP_BASEMUL, groups, outs), d)
        return d[2 * N:]


def make_host(design="A", shuffle=False, record=False, seed=None):
    return Host(ChipA() if design == "A" else ChipB(), shuffle=shuffle, record=record, seed=seed)
