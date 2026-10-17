"""Design B: design A's stream engine plus a 16-coefficient block engine, at pin level.

Every frame starts with a header word (valid=1, sof=1), see protocol.header().
  stream mode (din[2]=0): A's transactions follow; op comes from the op pins (held for the frame).
  block mode  (din[2]=1): 16 data words on the next 16 clocks, fixed compute time, 24 bytes out.

Shuffle: a free-running 16-bit Galois LFSR (taps 0xB400, reset 0xACE1) advances every clock. At the
start of each local layer the chip takes m = lfsr[2:0], r = lfsr[5:3] and runs that layer's 8
butterflies in order k' = ((k ^ m) + r) mod 8. Results and timing do not depend on it.
"""
from chip_a import ProtocolError, StreamEngine
from mlkem_ntt_model import b_run_block
from pins import PinIn
from protocol import BLOCK_WORDS, block_lat, block_period, parse_header

LFSR_SEED, LFSR_TAPS = 0xACE1, 0xB400


class ChipB(StreamEngine):
    def __init__(self, mult="serial"):
        super().__init__(mult)
        self.lfsr = LFSR_SEED
        self.lfsr_at = {}           # cycle -> LFSR value, only kept while a block computes
        self.blk = None             # block being received: dict(h, hdr, words)
        self.pending = []           # blocks waiting for their compute window to pass
        self.orders = []            # debug: butterfly orders used by the last block

    def step(self, ui_in, uio_in):
        p = PinIn.decode(ui_in, uio_in)
        t = self.cycle
        if self.pending:
            self.lfsr_at[t] = self.lfsr
            self.finish_blocks(t)
        out = self.output()

        if p.sof and not p.valid:
            raise ProtocolError(f"cycle {t}: sof without valid")
        if p.valid and p.sof:
            self.header(t, p)
        elif self.blk is not None:
            if not p.valid or t != self.blk["h"] + 1 + len(self.blk["words"]):
                raise ProtocolError(f"cycle {t}: block words must be on 16 consecutive clocks")
            self.blk["words"].append(p.din)
            if len(self.blk["words"]) == BLOCK_WORDS:
                self.pending.append(self.blk)
                self.blk = None
        elif p.valid:
            if self.frame_op is None:
                raise ProtocolError(f"cycle {t}: data before any header")
            self.stream_word(t, p.din, p.op)
        else:
            self.check_idle(t)

        # Galois LFSR, one step per clock
        self.lfsr = (self.lfsr >> 1) ^ (LFSR_TAPS if self.lfsr & 1 else 0)
        self.cycle += 1
        return out

    def header(self, t, p):
        if self.cur or self.blk is not None:
            raise ProtocolError(f"cycle {t}: header inside a transaction")
        hdr = parse_header(p.din)
        if hdr["reserved"]:
            raise ProtocolError(f"cycle {t}: header din[11:8] must be 0")
        if hdr["block_mode"]:
            if t < self.next_ok:
                raise ProtocolError(f"cycle {t}: block header before cycle {self.next_ok}")
            self.blk = {"h": t, "hdr": hdr, "words": []}
            self.next_ok = t + block_period(hdr["pass_id"], self.mult)
            self.frame_op = None
        else:
            self.reset_counters()
            self.frame_op = p.op

    def finish_blocks(self, t):
        """Compute a block once its last local layer has started (all LFSR draws are known).
        Its bytes are due at c0 + compute, which is always later than that."""
        for b in list(self.pending):
            h, hdr = b["h"], b["hdr"]
            pid = hdr["pass_id"]
            c0 = h + 1 + BLOCK_WORDS                      # first compute cycle
            nl = 4 if pid in (0, 3) else 3
            per_layer = 8 * (3 if self.mult == "serial" else 1)
            if t < c0 + (nl - 1) * per_layer:
                continue
            orders = []
            for ll in range(nl):
                if hdr["shuffle"]:
                    v = self.lfsr_at[c0 + ll * per_layer]
                    m, r = v & 7, (v >> 3) & 7
                    orders.append([((k ^ m) + r) & 7 for k in range(8)])
                else:
                    orders.append(list(range(8)))
            self.orders = orders
            res = b_run_block(b["words"], pid, hdr["blk"], lambda ll: orders[ll])
            first = h + block_lat(pid, self.mult)
            for i in range(8):
                self.emit(first + 3 * i, (res[2 * i], res[2 * i + 1]))
            self.pending.remove(b)
        if not self.pending:
            self.lfsr_at.clear()
