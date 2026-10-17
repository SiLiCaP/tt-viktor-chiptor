/*
 * modq_acc (team Spec 4): registered running sum mod 3329.
 *   ld  : acc <= y          add : acc <= (acc + y) mod 3329        ld wins; neither: hold
 * acc is valid one clock after ld or add.
 */

`default_nettype none

module modq_acc (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        ld,
    input  wire        add,
    input  wire [11:0] y,
    output reg  [11:0] acc
);
  localparam [12:0] Q = 13'd3329;

  wire [12:0] s  = {1'b0, acc} + {1'b0, y};
  wire [13:0] sc = {1'b0, s} - {1'b0, Q};
  wire [11:0] sum = sc[13] ? s[11:0] : sc[11:0];
  wire _unused = &{sc[12], 1'b0};

  always @(posedge clk) begin
    if (!rst_n)   acc <= 12'd0;
    else if (ld)  acc <= y;
    else if (add) acc <= sum;
  end
endmodule
