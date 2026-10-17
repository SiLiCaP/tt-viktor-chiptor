"""ML-KEM backend whose polynomial arithmetic runs on the chip in the Tang Nano (or on the Python model).

Unlike a trace replay, this is the real coprocessor loop: the PC sends one NTT layer, reads the board's
results back, and builds the next layer from them. The chip keeps its counters while its clock is
paused between batches (valid low changes nothing, docs/PROTOCOL.md).

    from board import BoardBackend
    be = BoardBackend(TTEmu())             # or BoardBackend(SimEmu()) without a board
    MLKEM768(backend=be).keygen_internal(d, z)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "model")]

from chip_a import ChipA  # noqa: E402
from chip_arith import FACTOR  # noqa: E402
from pins import PinIn  # noqa: E402
from protocol import LAT, OFFSETS, OP_BASEMUL, OP_CT, OP_GS, OP_SCALE, PERIOD, unpack_pair  # noqa: E402


class SimEmu:
    """Stands in for TTEmu with the cycle-accurate chip model, for rehearsing without a board."""
    port = "simulation"

    def __init__(self):
        self.chip = ChipA()

    def ping(self):
        return b"SIM "

    def set_inputs(self, ui, uio):
        pass

    def set_div(self, d):
        pass

    def reset(self, n=10):
        self.chip = ChipA()

    def run_stream(self, words):
        return [(self.chip.step(w & 0xFF, w >> 8), 0, 0) for w in words]


class BoardBackend:
    factor = FACTOR

    def __init__(self, emu, log_first=False):
        self.emu = emu
        self.emu.set_inputs(0, 0)
        self.emu.reset(10)
        self.clocks = {}                 # op -> DUT clocks streamed
        self.calls = {}
        self.first_batch = None          # (op, stim, uo) of the first batch, for the timing figure
        self.log_first = log_first

    def _batch(self, op, units, sof):
        """units: list of input-value lists. Streams them at the protocol period, plus a tail so the
        last results come out, and returns one result pair per unit."""
        period, lat, offs = PERIOD[op], LAT[op], OFFSETS[op]
        stim = [0] * (len(units) * period + lat + 3)
        for k, vals in enumerate(units):
            for i, (off, v) in enumerate(zip(offs, vals)):
                stim[k * period + off] = PinIn(v, True, sof and k == 0 and i == 0, op).word16()
        caps = self.emu.run_stream(stim)
        uo = [c[0] for c in caps]
        if self.log_first and self.first_batch is None:
            self.first_batch = (op, stim, uo)
        self.clocks[op] = self.clocks.get(op, 0) + len(stim)
        out = []
        for k in range(len(units)):
            v = unpack_pair(*uo[k * period + lat:k * period + lat + 3])
            if max(v) >= 3329:
                raise IOError(f"result {v} out of range: hardware fault")
            out.append(v)
        return out

    def _butterflies(self, op, f, inverse):
        f = list(f)
        self.calls[op] = self.calls.get(op, 0) + 1
        for layer in range(7):                           # one batch per layer
            L = (2 << layer) if inverse else (128 >> layer)
            pairs = [(j, j + L) for start in range(0, 256, 2 * L) for j in range(start, start + L)]
            res = self._batch(op, [(f[hi], f[lo]) for lo, hi in pairs], sof=(layer == 0))
            for (lo, hi), (r0, r1) in zip(pairs, res):
                f[lo], f[hi] = r0, r1
        return f

    def ntt(self, f):
        return self._butterflies(OP_CT, f, False)

    def invntt(self, f):
        return self._butterflies(OP_GS, f, True)

    def basemul(self, f, g):
        self.calls[OP_BASEMUL] = self.calls.get(OP_BASEMUL, 0) + 1
        res = self._batch(OP_BASEMUL, [(g[2 * i + 1], f[2 * i + 1], g[2 * i], f[2 * i]) for i in range(128)], True)
        return [x for pair in res for x in pair]

    def scale(self, f):
        self.calls[OP_SCALE] = self.calls.get(OP_SCALE, 0) + 1
        res = self._batch(OP_SCALE, [(f[2 * i], f[2 * i + 1]) for i in range(128)], True)
        return [x for pair in res for x in pair]
