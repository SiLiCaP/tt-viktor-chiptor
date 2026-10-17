"""Cycle-accurate Python models of DUTs the emulator can run, shared by fpga/sim and host tests.

Convention (matches the wrapper and cocotb): for each clock, the host applies (ui, uio), then
samples outputs just before the rising edge, then the edge happens. So
    out[i] = f(inputs[i], state after i rising edges).
"""


class ExampleModel:
    """The template's example design: uo_out = ui_in + uio_in (combinational)."""
    name = "tt_um_example"

    def reset(self):
        pass

    def cycle(self, ui, uio):
        return ((ui + uio) & 0xFF, 0, 0)


class SelftestModel:
    """fpga/sim/tt_um_emu_selftest.v: registered XOR, cycle counter, combinational echo."""
    name = "tt_um_emu_selftest"

    def reset(self):
        self.r = 0
        self.cnt = 0

    def cycle(self, ui, uio):
        out = (self.r, self.cnt, ui)
        self.r = ui ^ uio
        self.cnt = (self.cnt + 1) & 0xFF
        return out


def run_model(model, words):
    """Stimulus words {uio_in, ui_in} -> expected (uo_out, uio_out, uio_oe) per clock."""
    return [model.cycle(w & 0xFF, w >> 8) for w in words]


MODELS = {"tt_um_example": ExampleModel,
          "tt_um_emu_selftest": SelftestModel}
# tt_um_ntt_engine is checked by replaying protocol-legal stimulus files (host/test_ntt.py), not random words.
