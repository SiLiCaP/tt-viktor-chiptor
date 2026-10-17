// Exhaustive modq_mul check (team Spec 2): all 3329 x 3329 pairs, back to back (a start every 3
// clocks), each result exactly 4 clocks after its start. Run: make -C test/units mul_exh
`default_nettype none
`timescale 1ns / 1ps
module tb_modq_mul_exh;
  reg clk = 0, rst_n = 0, start = 0, flush = 0;
  reg [11:0] a_in = 0, b_in = 0;
  wire [11:0] p_out; wire p_valid, ready;
  modq_mul dut (.clk(clk), .rst_n(rst_n), .start(start), .a_in(a_in), .b_in(b_in),
                .flush(flush), .p_out(p_out), .p_valid(p_valid), .ready(ready));
  always #5 clk = ~clk;

  integer a, b, errors = 0, n = 0;
  reg [11:0] exp_q [0:7];      // expected results in flight, indexed by start number
  integer cyc = 0, last_start = -100;
  reg [63:0] start_cyc [0:7];
  integer head = 0, tail = 0;

  always @(posedge clk) begin
    cyc <= cyc + 1;
    if (p_valid) begin
      if (p_out !== exp_q[head % 8] || cyc != start_cyc[head % 8] + 4) begin
        errors = errors + 1;
        if (errors < 10) $display("MISMATCH start#%0d: got %0d at +%0d, expected %0d at +4",
                                  head, p_out, cyc - start_cyc[head % 8], exp_q[head % 8]);
      end
      head = head + 1;
    end
  end

  integer lo = 0, hi = 3329;
  initial begin
    if ($value$plusargs("LO=%d", lo)) ;
    if ($value$plusargs("HI=%d", hi)) ;
    repeat (3) @(negedge clk);
    rst_n = 1;
    for (a = lo; a < hi; a = a + 1) begin
      for (b = 0; b < 3329; b = b + 1) begin
        @(negedge clk);
        if (!ready) begin $display("ready low when a start is due"); errors = errors + 1; end
        start = 1; a_in = a; b_in = b;
        exp_q[tail % 8] = (64'd169 * a * b) % 3329;
        start_cyc[tail % 8] = cyc;
        tail = tail + 1;
        @(negedge clk); start = 0;
        @(negedge clk);
      end
    end
    repeat (8) @(negedge clk);
    if (head != tail) begin $display("lost results: %0d of %0d", head, tail); errors = errors + 1; end
    if (errors == 0) $display("PASS [%0d,%0d): %0d products, latency 4, one start per 3 clocks", lo, hi, tail);
    else $display("FAIL: %0d errors", errors);
    $finish;
  end
endmodule
