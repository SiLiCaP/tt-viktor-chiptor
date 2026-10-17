/*
 * io_out_pack (team Spec 5): a result pair -> 3 bytes on 3 consecutive clocks, ML-KEM ByteEncode12.
 *   clock after pair_valid +1: r0[7:0]   +2: {r1[3:0], r0[11:8]}   +3: r1[11:4]   then 0x00
 * flush drops pending bytes: uo_byte is 0x00 from the next clock (flush wins over pair_valid).
 * uo_byte is a register output. Latency to the first byte: 1 clock.
 */

`default_nettype none

module io_out_pack (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        pair_valid,
    input  wire [11:0] r0,
    input  wire [11:0] r1,
    input  wire        flush,
    output reg  [7:0]  uo_byte
);
  reg [15:0] rest;     // bytes 2 and 3 still to send
  reg [1:0]  left;

  always @(posedge clk) begin
    if (!rst_n || flush) begin
      uo_byte <= 8'd0; rest <= 16'd0; left <= 2'd0;
    end else if (pair_valid) begin
      uo_byte <= r0[7:0];
      rest    <= {r1, r0[11:8]};
      left    <= 2'd2;
    end else if (left != 2'd0) begin
      uo_byte <= rest[7:0];
      rest    <= {8'd0, rest[15:8]};
      left    <= left - 2'd1;
    end else begin
      uo_byte <= 8'd0;
    end
  end

`ifdef SIM_ASSERT
  // Spec 5: pair_valid pulses at least 3 clocks apart
  reg [1:0] since;
  always @(posedge clk) begin
    if (!rst_n) since <= 2'd3;
    else if (pair_valid) begin
      if (since < 2'd2) begin $display("ASSERT io_out_pack: pair_valid closer than 3 clocks"); $fatal; end
      since <= 2'd0;
    end else if (since != 2'd3) since <= since + 2'd1;
  end
`endif
endmodule
