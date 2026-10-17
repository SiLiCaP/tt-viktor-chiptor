"""Design B (EXPERIMENTAL, not in the team plan): design A's stream engine plus a 16-coefficient
block engine, at pin level. Kept to evaluate a faster/bigger chip if more tiles are negotiated.

Every frame starts with a header word (valid=1, sof=1), see protocol.header().
  stream mode (din[2]=0): starts a design-A job with op from the op pins; the header is not an input.
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
    def __init__(self):
        super().__init__()
        self.lfsr = LFSR_SEED
        self.lfsr_at = {}
        self.blk = None
        self.pending = []
        self.orders = []
        self.block_next_ok = -1

    def step(self, ui_in, uio_in):
        p = PinIn.decode(ui_in, uio_in)
        t = self.cycle
        if self.pending:
            self.lfsr_at[t] = self.lfsr
            self.finish_blocks(t)
        out = self.output()

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
            self.take(t, p.din)
        elif self.job_op is not None:
            self.check_unit_gap(t)

        self.lfsr = (self.lfsr >> 1) ^ (LFSR_TAPS if self.lfsr & 1 else 0)
        self.cycle += 1
        return out

    def header(self, t, p):
        if self.blk is not None:
            raise ProtocolError(f"cycle {t}: header inside a block")
        hdr = parse_header(p.din)
        if hdr["reserved"]:
            raise ProtocolError(f"cycle {t}: header din[11:8] must be 0")
        if hdr["block_mode"]:
            if t < max(self.block_next_ok, self.next_ok):
                raise ProtocolError(f"cycle {t}: block header too early")
            self.job_op = None
            self.blk = {"h": t, "hdr": hdr, "words": []}
            self.block_next_ok = t + block_period(hdr["pass_id"])
        else:
            self.start_job(t, p.op)
            self.next_ok = self.block_next_ok

    def finish_blocks(self, t):
        for b in list(self.pending):
            h, hdr = b["h"], b["hdr"]
            pid = hdr["pass_id"]
            c0 = h + 1 + BLOCK_WORDS
            nl = 4 if pid in (0, 3) else 3
            per_layer = 24
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
            first = h + block_lat(pid)
            for i in range(8):
                for j, byte in enumerate([res[2 * i] & 0xFF, ((res[2 * i + 1] & 0xF) << 4) | (res[2 * i] >> 8),
                                          res[2 * i + 1] >> 4]):
                    self.sched[first + 3 * i + j] = byte
            self.pending.remove(b)
        if not self.pending:
            self.lfsr_at.clear()
