<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This is a coprocessor for the polynomial arithmetic in ML-KEM (FIPS 203, the NIST post-quantum key
encapsulation standard). The host (the RP2350 on the demo board) runs ML-KEM itself and offloads the
number-theoretic transform (NTT), the inverse NTT, base multiplication and scaling, all modulo
q = 3329. The 128 twiddle factors are in an on-chip ROM.

The host streams 12-bit coefficients in on `ui_in` and `uio_in[3:0]`, with `valid`, `sof` (start of
frame) and a 2-bit `op` on `uio_in[7:4]`. Results come back on `uo_out` as ML-KEM ByteEncode12 bytes.
There is no handshake: every result appears at a fixed, data-independent clock offset, so the chip
runs in constant time. The exact frame formats and latencies are in
[docs/PROTOCOL.md](PROTOCOL.md).

Inside: a 4-bit digit-serial modular multiplier with K-RED reduction (one product every 3 clocks),
modular adders and accumulators, a 128-entry twiddle ROM, and a control block that counts butterflies
and basemul pieces. Throughput: one butterfly every 3 clocks (about 2,700 clocks per NTT), one basemul
piece every 15 clocks. The design has run complete ML-KEM-768 key exchanges, cycle-exact, in simulation
and on an FPGA.

## How to test

Drive the pins in lockstep from the RP2350 (PIO) using the protocol in `docs/PROTOCOL.md`. The
`sim/` directory has a cycle-accurate Python model and a host driver, and `test/stimulus/` has
per-clock input and expected-output files you can replay.

## External hardware

None. Everything runs from the Tiny Tapeout demo board's RP2350.
