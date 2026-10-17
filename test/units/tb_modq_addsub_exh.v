// Exhaustive modq_addsub check (team Spec 4) for REG_OUT = 0 and 1: all 3329 x 3329 pairs.
`default_nettype none
`timescale 1ns / 1ps
module tb_modq_addsub_exh;
  reg clk = 0, rst_n = 0;
  reg [11:0] x = 0, y = 0;
  wire [11:0] s0, d0, s1, d1;
  modq_addsub #(.REG_OUT(0)) u0 (.clk(clk), .rst_n(rst_n), .x(x), .y(y), .sum(s0), .diff(d0));
  modq_addsub #(.REG_OUT(1)) u1 (.clk(clk), .rst_n(rst_n), .x(x), .y(y), .sum(s1), .diff(d1));
  always #5 clk = ~clk;
  integer i, j, errors = 0;
  reg [11:0] es, ed;
  integer lo = 0, hi = 3329;
  initial begin
    if ($value$plusargs("LO=%d", lo)) ;
    if ($value$plusargs("HI=%d", hi)) ;
    @(negedge clk); rst_n = 1;
    for (i = lo; i < hi; i = i + 1)
      for (j = 0; j < 3329; j = j + 1) begin
        x = i; y = j;
        es = (i + j) % 3329; ed = (i - j + 3329) % 3329;
        #1;
        if (s0 !== es || d0 !== ed) begin errors = errors + 1; if (errors < 10) $display("comb %0d %0d -> %0d %0d", i, j, s0, d0); end
        @(negedge clk);
        if (s1 !== es || d1 !== ed) begin errors = errors + 1; if (errors < 10) $display("reg %0d %0d -> %0d %0d", i, j, s1, d1); end
      end
    if (errors == 0) $display("PASS [%0d,%0d): %0d pairs, REG_OUT 0 and 1", lo, hi, (hi - lo) * 3329);
    else $display("FAIL: %0d errors", errors);
    $finish;
  end
endmodule
