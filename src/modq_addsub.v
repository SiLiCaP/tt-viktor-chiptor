/*
 * modq_addsub (team Spec 4): sum = (x + y) mod 3329 and diff = (x - y) mod 3329 together.
 * REG_OUT = 0: combinational (latency 0). REG_OUT = 1: registered outputs (latency 1).
 * Inputs must be in 0..3328; one conditional correction per output.
 */

`default_nettype none

module modq_addsub #(
    parameter REG_OUT = 0
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [11:0] x,
    input  wire [11:0] y,
    output wire [11:0] sum,
    output wire [11:0] diff
);
  localparam [12:0] Q = 13'd3329;

  wire [12:0] s  = {1'b0, x} + {1'b0, y};          // 0 .. 6656
  wire [13:0] sc = {1'b0, s} - {1'b0, Q};           // negative (bit 13) when s < q
  wire [11:0] sum_c = sc[13] ? s[11:0] : sc[11:0];

  wire [12:0] d  = {1'b0, x} - {1'b0, y};           // negative (bit 12) when x < y
  wire [12:0] dc = d + Q;
  wire [11:0] diff_c = d[12] ? dc[11:0] : d[11:0];
  wire _unused_bits = &{sc[12], dc[12], 1'b0};

  generate
    if (REG_OUT) begin : g_reg
      reg [11:0] sum_r, diff_r;
      always @(posedge clk) begin
        if (!rst_n) begin
          sum_r <= 12'd0; diff_r <= 12'd0;
        end else begin
          sum_r <= sum_c; diff_r <= diff_c;
        end
      end
      assign sum = sum_r;
      assign diff = diff_r;
    end else begin : g_comb
      assign sum = sum_c;
      assign diff = diff_c;
      wire _unused = &{clk, rst_n, 1'b0};
    end
  endgenerate
endmodule
