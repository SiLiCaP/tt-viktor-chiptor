"""One clock of the 24 Tiny Tapeout project pins, as the NTT coprocessor uses them.

    ui_in[7:0], uio_in[3:0]  din (12-bit word)      uio_in[4] valid
    uio_in[5]  sof           uio_in[7:6] op          uo_out[7:0] result byte
    uio_out = 0, uio_oe = 0 (all bidirectional pins are inputs)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PinIn:
    din: int = 0
    valid: bool = False
    sof: bool = False
    op: int = 0

    def encode(self):
        """-> (ui_in, uio_in)"""
        assert 0 <= self.din < 4096 and 0 <= self.op < 4
        return self.din & 0xFF, (self.din >> 8) | (self.valid << 4) | (self.sof << 5) | (self.op << 6)

    @staticmethod
    def decode(ui_in, uio_in):
        return PinIn(din=((uio_in & 0xF) << 8) | ui_in, valid=bool(uio_in >> 4 & 1),
                     sof=bool(uio_in >> 5 & 1), op=uio_in >> 6)

    def word16(self):
        """Stimulus-file word {uio_in, ui_in}, as the Tang Nano rig and cocotb replay it."""
        ui, uio = self.encode()
        return (uio << 8) | ui


IDLE = PinIn()


def frame(chip, pin_in):
    """One clock: (ui_in, uio_in) -> (uo_out, uio_out, uio_oe)."""
    ui, uio = pin_in.encode()
    return chip.step(ui, uio), 0, 0
