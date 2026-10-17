/*
 * Copyright (c) 2026 Marks Hansons
 * SPDX-License-Identifier: Apache-2.0
 *
 * ML-KEM (FIPS 203) NTT coprocessor, Tiny Tapeout shell (team Spec 5).
 * Pins: din = {uio_in[3:0], ui_in}, valid = uio_in[4], sof = uio_in[5], op = uio_in[7:6];
 * results on uo_out as ByteEncode12 bytes at fixed delays (docs/PROTOCOL.md).
 * All uio pins are inputs.
 */

`default_nettype none

module tt_um_ntt_engine (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  wire [11:0] coeff_q;
  wire        valid_q, sof_q;
  wire [1:0]  op_q;
  io_in_capture u_in (.clk(clk), .rst_n(rst_n), .ui_in(ui_in), .uio_in(uio_in),
                      .coeff_q(coeff_q), .valid_q(valid_q), .sof_q(sof_q), .op_q(op_q));

  wire [11:0] r0, r1;
  wire        pair_valid, flush;
  ntt_core u_core (.clk(clk), .rst_n(rst_n), .coeff_q(coeff_q), .valid_q(valid_q), .sof_q(sof_q),
                   .op_q(op_q), .r0(r0), .r1(r1), .pair_valid(pair_valid), .flush(flush));

  io_out_pack u_out (.clk(clk), .rst_n(rst_n), .pair_valid(pair_valid), .r0(r0), .r1(r1),
                     .flush(flush), .uo_byte(uo_out));

  assign uio_out = 8'h00;
  assign uio_oe  = 8'h00;

  wire _unused = &{ena, 1'b0};

endmodule
