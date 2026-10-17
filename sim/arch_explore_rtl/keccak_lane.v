// Lane-serial Keccak-f[1600] (exploration for the hasher-engine spec; verified against keccak_ref.py).
//   one 64-bit lane read + one lane write per clock, state = 25 x 64-bit registers
//   theta parities are accumulated while chi writes the previous round (one 25-clock pass before round 0)
//   rho + pi in place: walk pi's single 24-lane cycle with one temp lane and a 64-bit rotator
//   chi + iota row by row through a 5-lane window (+2 saved lanes for the row wrap)
//   25 + 24 x 56 = 1,369 clocks per permutation, fixed (data-independent)
`default_nettype none

module keccak_lane (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,          // begin a permutation (ignored while busy)
    output reg         busy,
    input  wire        io_we,          // when idle: A[io_idx] ^= io_wdata (absorb)
    input  wire [4:0]  io_idx,
    input  wire [63:0] io_wdata,
    output wire [63:0] io_rdata        // when idle: A[io_idx] (squeeze)
);
  reg [63:0] A [0:24];
  reg [63:0] C [0:4];
  reg [63:0] W [0:4];
  reg [63:0] S0, S1, tmp;
  reg [1:0]  phase;                    // 0 parity pass, 1 theta lane 0 + rho/pi walk, 2 chi
  reg [4:0]  rnd, k;                   // round; step inside the phase

  function [4:0] cyc(input [4:0] n);
    case (n)
      5'd0: cyc = 5'd1;
      5'd1: cyc = 5'd10;
      5'd2: cyc = 5'd7;
      5'd3: cyc = 5'd11;
      5'd4: cyc = 5'd17;
      5'd5: cyc = 5'd18;
      5'd6: cyc = 5'd3;
      5'd7: cyc = 5'd5;
      5'd8: cyc = 5'd16;
      5'd9: cyc = 5'd8;
      5'd10: cyc = 5'd21;
      5'd11: cyc = 5'd24;
      5'd12: cyc = 5'd4;
      5'd13: cyc = 5'd15;
      5'd14: cyc = 5'd23;
      5'd15: cyc = 5'd19;
      5'd16: cyc = 5'd13;
      5'd17: cyc = 5'd12;
      5'd18: cyc = 5'd2;
      5'd19: cyc = 5'd20;
      5'd20: cyc = 5'd14;
      5'd21: cyc = 5'd22;
      5'd22: cyc = 5'd9;
      5'd23: cyc = 5'd6;
      default: cyc = 5'd0;
    endcase
  endfunction
  function [5:0] rho(input [4:0] i);
    case (i)
      5'd0: rho = 6'd0;
      5'd1: rho = 6'd1;
      5'd2: rho = 6'd62;
      5'd3: rho = 6'd28;
      5'd4: rho = 6'd27;
      5'd5: rho = 6'd36;
      5'd6: rho = 6'd44;
      5'd7: rho = 6'd6;
      5'd8: rho = 6'd55;
      5'd9: rho = 6'd20;
      5'd10: rho = 6'd3;
      5'd11: rho = 6'd10;
      5'd12: rho = 6'd43;
      5'd13: rho = 6'd25;
      5'd14: rho = 6'd39;
      5'd15: rho = 6'd41;
      5'd16: rho = 6'd45;
      5'd17: rho = 6'd15;
      5'd18: rho = 6'd21;
      5'd19: rho = 6'd8;
      5'd20: rho = 6'd18;
      5'd21: rho = 6'd2;
      5'd22: rho = 6'd61;
      5'd23: rho = 6'd56;
      5'd24: rho = 6'd14;
      default: rho = 6'd0;
    endcase
  endfunction
  function [63:0] rc(input [4:0] r);
    case (r)
      5'd0: rc = 64'h0000000000000001;
      5'd1: rc = 64'h0000000000008082;
      5'd2: rc = 64'h800000000000808a;
      5'd3: rc = 64'h8000000080008000;
      5'd4: rc = 64'h000000000000808b;
      5'd5: rc = 64'h0000000080000001;
      5'd6: rc = 64'h8000000080008081;
      5'd7: rc = 64'h8000000000008009;
      5'd8: rc = 64'h000000000000008a;
      5'd9: rc = 64'h0000000000000088;
      5'd10: rc = 64'h0000000080008009;
      5'd11: rc = 64'h000000008000000a;
      5'd12: rc = 64'h000000008000808b;
      5'd13: rc = 64'h800000000000008b;
      5'd14: rc = 64'h8000000000008089;
      5'd15: rc = 64'h8000000000008003;
      5'd16: rc = 64'h8000000000008002;
      5'd17: rc = 64'h8000000000000080;
      5'd18: rc = 64'h000000000000800a;
      5'd19: rc = 64'h800000008000000a;
      5'd20: rc = 64'h8000000080008081;
      5'd21: rc = 64'h8000000000008080;
      5'd22: rc = 64'h0000000080000001;
      5'd23: rc = 64'h8000000080008008;
      default: rc = 64'd0;
    endcase
  endfunction
  function [63:0] rotl(input [63:0] x, input [5:0] n);
    rotl = (x << n) | (x >> (7'd64 - {1'b0, n}));
  endfunction
  function [2:0] xof(input [4:0] i);   // i mod 5
    xof = i - 5'd5 * (i / 5'd5);
  endfunction

  // theta column effect, from the parities C
  wire [63:0] D0 = C[4] ^ rotl(C[1], 6'd1);
  wire [63:0] D1 = C[0] ^ rotl(C[2], 6'd1);
  wire [63:0] D2 = C[1] ^ rotl(C[3], 6'd1);
  wire [63:0] D3 = C[2] ^ rotl(C[4], 6'd1);
  wire [63:0] D4 = C[3] ^ rotl(C[0], 6'd1);
  function [63:0] dsel(input [2:0] x, input [63:0] d0, d1, d2, d3, d4);
    case (x) 3'd0: dsel = d0; 3'd1: dsel = d1; 3'd2: dsel = d2; 3'd3: dsel = d3; default: dsel = d4; endcase
  endfunction

  // walk step k (1..24): src = cyc[k-1], dest = cyc[k mod 24]; k = 0 is theta on lane 0
  wire [4:0] src  = cyc(k - 5'd1);
  wire [4:0] dest = (k == 5'd24) ? cyc(5'd0) : cyc(k);
  // chi step k (0..29): k < 5 loads row 0; k >= 5 writes lane j = k - 5 and loads the lane below it
  wire [4:0] j    = k - 5'd5;
  wire [2:0] cx   = xof(j);
  wire [4:0] crow = j - cx;                      // 5*y
  reg  [4:0] raddr;
  always @(*) begin
    if (!busy)                    raddr = io_idx;
    else if (phase == 2'd0)       raddr = k;
    else if (phase == 2'd1)       raddr = (k == 5'd0) ? 5'd0 : dest;
    else if (k < 5'd5)            raddr = k;
    else                          raddr = j + 5'd5;
  end
  wire [63:0] rdata = A[raddr];
  assign io_rdata = rdata;

  // chi output for lane j
  wire [63:0] w1 = (cx == 3'd4) ? S0 : (cx == 3'd3) ? W[4] : W[cx + 3'd1];
  wire [63:0] w2 = (cx == 3'd4) ? S1 : (cx == 3'd3) ? S0   : W[cx + 3'd2];
  wire [63:0] chi = W[cx] ^ (~w1 & w2) ^ ((j == 5'd0) ? rc(rnd) : 64'd0);

  // the one write port
  reg        we;
  reg [4:0]  waddr;
  reg [63:0] wdata;
  always @(*) begin
    we = 1'b0; waddr = 5'd0; wdata = 64'd0;
    if (!busy) begin
      we = io_we; waddr = io_idx; wdata = rdata ^ io_wdata;
    end else if (phase == 2'd1) begin
      we = 1'b1;
      if (k == 5'd0) begin waddr = 5'd0; wdata = rdata ^ D0; end
      else begin waddr = dest; wdata = rotl(tmp ^ dsel(xof(src), D0, D1, D2, D3, D4), rho(src)); end
    end else if (phase == 2'd2 && k >= 5'd5) begin
      we = 1'b1; waddr = j; wdata = chi;
    end
  end

  integer i;
  always @(posedge clk) begin
    if (!rst_n) begin
      for (i = 0; i < 25; i = i + 1) A[i] <= 64'd0;
      for (i = 0; i < 5; i = i + 1) begin C[i] <= 64'd0; W[i] <= 64'd0; end
      S0 <= 64'd0; S1 <= 64'd0; tmp <= 64'd0; busy <= 1'b0; phase <= 2'd0; rnd <= 5'd0; k <= 5'd0;
    end else begin
      if (we) A[waddr] <= wdata;
      if (!busy) begin
        if (start) begin
          busy <= 1'b1; phase <= 2'd0; rnd <= 5'd0; k <= 5'd0;
          for (i = 0; i < 5; i = i + 1) C[i] <= 64'd0;
        end
      end else case (phase)
        2'd0: begin                                   // parity pass
          C[xof(k)] <= C[xof(k)] ^ rdata;
          if (k == 5'd24) begin phase <= 2'd1; k <= 5'd0; end else k <= k + 5'd1;
        end
        2'd1: begin                                   // theta lane 0, then rho/pi walk
          if (k == 5'd0) begin tmp <= A[cyc(5'd0)]; k <= 5'd1; end
          else begin
            tmp <= rdata;
            if (k == 5'd24) begin phase <= 2'd2; k <= 5'd0; end else k <= k + 5'd1;
          end
        end
        default: begin                                // chi + iota, parities for the next round
          if (k < 5'd5) begin
            W[k] <= rdata;
            if (k == 5'd0) for (i = 0; i < 5; i = i + 1) C[i] <= 64'd0;
          end else begin
            C[cx] <= C[cx] ^ chi;
            if (crow != 5'd20) W[cx] <= rdata;
            if (cx == 3'd0) S0 <= W[0];
            if (cx == 3'd1) S1 <= W[1];
          end
          if (k == 5'd29) begin
            k <= 5'd0;
            if (rnd == 5'd23) busy <= 1'b0;
            else begin rnd <= rnd + 5'd1; phase <= 2'd1; end
          end else k <= k + 5'd1;
        end
      endcase
    end
  end
endmodule
