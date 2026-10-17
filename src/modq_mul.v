/*
 * modq_mul (team Spec 2): p_out = (169 * a_in * b_in) mod 3329.
 *
 * 4-bit digit-serial over b, least significant digit first: one 12x4 partial product per clock.
 *   start clock  s   : acc = a * b[3:0]
 *   s+1              : acc += a * b[7:4]  << 4
 *   s+2              : acc += a * b[11:8] << 8   (full 24-bit product now in acc)
 *   s+3              : two K-RED rounds + one correction, registered into p_out
 *   s+4              : p_valid high for one clock                       -> latency 4
 * A new start is accepted every 3 clocks; at clock s+3 the next operation loads acc while the
 * reduction stage still reads the finished product.
 *
 * K-RED (q = 13*2^8 + 1): kred(x) = 13*x[7:0] - (x >> 8) is congruent to 13*x. Two rounds give
 * 169*x; after round 2 the value is in -12..3484, so one add or subtract of q finishes it.
 */

`default_nettype none

module modq_mul (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [11:0] a_in,
    input  wire [11:0] b_in,
    input  wire        flush,
    output reg  [11:0] p_out,
    output reg         p_valid,
    output wire        ready
);
  localparam [11:0] Q = 12'd3329;

  reg  [11:0] ra;
  reg  [7:0]  rb_hi;        // b[11:4], still to be consumed
  reg  [23:0] acc;
  reg  [1:0]  phase;        // 0 idle, 1 and 2 digit clocks, 3 product ready in acc

  wire [15:0] pp_first = a_in * b_in[3:0];
  wire [3:0]  digit    = (phase == 2'd1) ? rb_hi[3:0] : rb_hi[7:4];
  wire [15:0] pp       = ra * digit;
  wire [23:0] pp_sh    = (phase == 2'd1) ? {4'd0, pp, 4'd0} : {pp, 8'd0};

  // ---- K-RED, two rounds, on the finished product ----
  wire [11:0]        t1 = {4'd0, acc[7:0]} * 12'd13;                       // <= 3315
  wire signed [17:0] r1 = $signed({6'd0, t1}) - $signed({2'd0, acc[23:8]});   // -43264 .. 3315
  wire [11:0]        t2 = {4'd0, r1[7:0]} * 12'd13;
  wire signed [14:0] r2 = $signed({3'd0, t2}) - $signed({{5{r1[17]}}, r1[17:8]}); // -12 .. 3484
  wire signed [14:0] r2_lo = r2 + $signed({3'd0, Q});
  wire signed [14:0] r2_hi = r2 - $signed({3'd0, Q});
  wire [11:0] red = r2[14] ? r2_lo[11:0] : (r2_hi[14] ? r2[11:0] : r2_hi[11:0]);
  wire _unused = &{r2_lo[14:12], r2_hi[13:12], 1'b0};

  assign ready = (phase == 2'd0) || (phase == 2'd3);

  always @(posedge clk) begin
    if (!rst_n) begin
      ra <= 12'd0; rb_hi <= 8'd0; acc <= 24'd0; phase <= 2'd0;
      p_out <= 12'd0; p_valid <= 1'b0;
    end else begin
      // reduction stage: result of the operation that finished its digits
      p_valid <= (phase == 2'd3) && !flush;
      if (phase == 2'd3 && !flush) p_out <= red;

      // digit stage
      if (start) begin                      // an operation started on the flush clock survives
        ra    <= a_in;
        rb_hi <= b_in[11:4];
        acc   <= {8'd0, pp_first};
        phase <= 2'd1;
      end else if (flush) begin
        phase <= 2'd0;
      end else if (phase == 2'd1 || phase == 2'd2) begin
        acc   <= acc + pp_sh;
        phase <= phase + 2'd1;
      end else begin
        phase <= 2'd0;
      end
    end
  end
endmodule
