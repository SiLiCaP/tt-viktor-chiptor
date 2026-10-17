
module mul_par (input wire clk, input wire rst_n, input wire [11:0] a, input wire [11:0] b, output reg [11:0] p);
  wire [23:0] x = a * b;
  wire [11:0] t1 = {4'd0, x[7:0]} * 12'd13;
  wire signed [17:0] r1 = $signed({6'd0, t1}) - $signed({2'd0, x[23:8]});
  wire [11:0] t2 = {4'd0, r1[7:0]} * 12'd13;
  wire signed [14:0] r2 = $signed({3'd0, t2}) - $signed({{5{r1[17]}}, r1[17:8]});
  wire signed [14:0] lo = r2 + 15'sd3329, hi = r2 - 15'sd3329;
  always @(posedge clk) p <= !rst_n ? 12'd0 : (r2[14] ? lo[11:0] : (hi[14] ? r2[11:0] : hi[11:0]));
endmodule
