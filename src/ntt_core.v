/*
 * ntt_core (team Spec 3): job control, counters, ROM / gamma select, operand registers, muxes,
 * bypass delay and loop-back, around modq_mul, modq_addsub (Pre, Post) and modq_acc (x2).
 *
 * Timing below is in clocks of the captured inputs (*_q), u = clock of a unit's first input.
 * Pin timing is one clock earlier; docs/PROTOCOL.md has the pin view (D = 6 / 7 / 20 / 9).
 *
 *   forward  b@u: start b*zeta'   a@u+1: opr1 <= a          p_valid@u+4: pair (a+t, a-t)
 *   inverse  b@u: opr0 <= b         a@u+1: start (b-a)*zeta', opr2 <= a+b, opr3 <= opr2 @u+3
 *                                                          p_valid@u+5: pair (opr3, product)
 *   basemul  g1@u opr0, f1@u+1 opr1 + pass1 f1*g1, g0@u+2 opr2, f0@u+3 opr3
 *            passes every 3 clocks: u+4 f0*g0, u+7 m1*gamma' (loop-back of p_out), u+10 f0*g1,
 *            u+13 f1*g0. Results m1@u+5 m3@u+8 m2@u+11 m4@u+14 m5@u+17 -> acc0 = m3+m2,
 *            acc1 = m4+m5, pair@u+18.
 *   scale    c@u: start c*1441; first result of a pair held in opr0, pair on the second.
 *
 * A job starts on valid_q & sof_q (that coefficient is input 0), runs a fixed number of inputs,
 * then ignores extra inputs. Every sof flushes the multiplier and the output packer.
 */

`default_nettype none

module ntt_core (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [11:0] coeff_q,
    input  wire        valid_q,
    input  wire        sof_q,
    input  wire [1:0]  op_q,
    output reg  [11:0] r0,
    output reg  [11:0] r1,
    output reg         pair_valid,
    output wire        flush
);
  localparam [1:0] FWD = 2'd0, INV = 2'd1, BM = 2'd2, SC = 2'd3;
  localparam [11:0] Q = 12'd3329, SCALE_C = 12'd1441;

  // ---------------- job control ----------------
  reg        active;           // still taking inputs
  reg [1:0]  op_r;
  reg [10:0] in_cnt;
  reg [1:0]  in_idx;           // input index inside a unit
  reg [2:0]  layer;
  reg [6:0]  bf;
  reg [6:0]  piece;

  wire job_start = valid_q & sof_q;
  assign flush = job_start;
  wire take = valid_q & (job_start | active);

  wire [1:0]  op     = job_start ? op_q : op_r;
  wire [1:0]  idx    = job_start ? 2'd0 : in_idx;
  wire [2:0]  layer_c = job_start ? 3'd0 : layer;
  wire [6:0]  bf_c    = job_start ? 7'd0 : bf;

  wire [10:0] job_len = (op == BM) ? 11'd512 : (op == SC) ? 11'd256 : 11'd1792;
  wire [10:0] cnt_c   = job_start ? 11'd0 : in_cnt;

  // ---------------- ROM, one instance ----------------
  wire [6:0] idx_fwd = (7'd1 << layer_c) | (bf_c >> (3'd7 - layer_c));
  wire [6:0] idx_inv = (7'd127 >> layer_c) - (bf_c >> (layer_c + 3'd1));
  wire [6:0] idx_bm  = {1'b1, piece[6:1]};
  wire [6:0] rom_idx = (op == FWD) ? idx_fwd : (op == INV) ? idx_inv : idx_bm;
  wire [11:0] zeta;
  zeta_rom u_rom (.idx(rom_idx), .zeta(zeta));
  wire [11:0] gamma = piece[0] ? (Q - zeta) : zeta;

  // ---------------- operand registers and adders ----------------
  reg  [11:0] opr0, opr1, opr2, opr3;
  wire [11:0] p_out;
  wire        p_valid;

  wire [11:0] pre_sum, pre_diff;            // inverse: x = b, y = a -> a+b, b-a
  modq_addsub #(.REG_OUT(0)) u_pre (.clk(clk), .rst_n(rst_n), .x(opr0), .y(coeff_q),
                                    .sum(pre_sum), .diff(pre_diff));
  wire [11:0] post_sum, post_diff;          // forward: x = a, y = t -> a+t, a-t
  modq_addsub #(.REG_OUT(0)) u_post (.clk(clk), .rst_n(rst_n), .x(opr1), .y(p_out),
                                     .sum(post_sum), .diff(post_diff));

  // ---------------- multiplier operand select ----------------
  reg  [2:0] pass;               // basemul: next pass 1..4 (0 = none)
  reg  [1:0] ptimer;
  wire       bm_pass = (op_r == BM) && (pass != 3'd0) && (ptimer == 2'd0) && !job_start;

  reg        m_start;
  reg [11:0] m_a, m_b;
  always @(*) begin
    m_start = 1'b0; m_a = coeff_q; m_b = zeta;
    if (take && op == FWD && idx == 2'd0) begin
      m_start = 1'b1; m_a = coeff_q; m_b = zeta;
    end else if (take && op == INV && idx == 2'd1) begin
      m_start = 1'b1; m_a = pre_diff; m_b = zeta;
    end else if (take && op == BM && idx == 2'd1) begin
      m_start = 1'b1; m_a = coeff_q; m_b = opr0;              // pass 1: f1 * g1
    end else if (take && op == SC) begin
      m_start = 1'b1; m_a = coeff_q; m_b = SCALE_C;
    end else if (bm_pass) begin
      m_start = 1'b1;
      case (pass)
        3'd1:    begin m_a = opr3;    m_b = opr2;    end         // f0 * g0
        3'd2:    begin m_a = p_out; m_b = gamma; end         // m1 * gamma' (loop-back)
        3'd3:    begin m_a = opr3;    m_b = opr0;    end         // f0 * g1
        default: begin m_a = opr1;    m_b = opr2;    end         // f1 * g0
      endcase
    end
  end

  wire m_ready;
  modq_mul u_mul (.clk(clk), .rst_n(rst_n), .start(m_start), .a_in(m_a), .b_in(m_b),
                  .flush(flush), .p_out(p_out), .p_valid(p_valid), .ready(m_ready));

  // ---------------- basemul accumulators ----------------
  reg  [2:0] res_idx;            // which basemul product p_valid carries: 0 m1, 1 m3, 2 m2, 3 m4, 4 m5
  reg        pair_pend;
  wire       bm_res = p_valid && (op_r == BM);
  wire [11:0] acc0, acc1;
  modq_acc u_acc0 (.clk(clk), .rst_n(rst_n), .ld(bm_res && res_idx == 3'd1),
                   .add(bm_res && res_idx == 3'd2), .y(p_out), .acc(acc0));
  modq_acc u_acc1 (.clk(clk), .rst_n(rst_n), .ld(bm_res && res_idx == 3'd3),
                   .add(bm_res && res_idx == 3'd4), .y(p_out), .acc(acc1));

  // ---------------- sequential control ----------------
  reg [1:0] inv_d;               // inverse: opr3 <= opr2 two clocks after the start
  reg       sc_odd;              // scale: first result of the pair is held

  always @(posedge clk) begin
    if (!rst_n) begin
      active <= 1'b0; op_r <= 2'd0; in_cnt <= 11'd0; in_idx <= 2'd0;
      layer <= 3'd0; bf <= 7'd0; piece <= 7'd0;
      opr0 <= 12'd0; opr1 <= 12'd0; opr2 <= 12'd0; opr3 <= 12'd0;
      pass <= 3'd0; ptimer <= 2'd0; res_idx <= 3'd0; pair_pend <= 1'b0;
      inv_d <= 2'd0; sc_odd <= 1'b0;
    end else begin
      if (job_start) begin
        op_r <= op_q;
        layer <= 3'd0; bf <= 7'd0; piece <= 7'd0;
        pass <= 3'd0; ptimer <= 2'd0; res_idx <= 3'd0; pair_pend <= 1'b0;
        inv_d <= 2'd0; sc_odd <= 1'b0;
      end

      // inputs
      if (take) begin
        in_cnt <= cnt_c + 11'd1;
        active <= (cnt_c + 11'd1 != job_len);
        in_idx <= (op == BM) ? idx + 2'd1 : {1'b0, ~idx[0]};
        case (op)
          FWD: if (idx[0]) opr1 <= coeff_q;
          INV: if (!idx[0]) opr0 <= coeff_q; else opr2 <= pre_sum;
          BM:  case (idx)
                 2'd0: opr0 <= coeff_q;
                 2'd1: opr1 <= coeff_q;
                 2'd2: opr2 <= coeff_q;
                 default: opr3 <= coeff_q;
               endcase
          default: ;
        endcase
        if ((op == FWD || op == INV) && idx[0]) begin
          bf <= bf_c + 7'd1;
          if (bf_c == 7'd127) layer <= layer_c + 3'd1;
        end
        if (op == BM && idx == 2'd1) begin
          pass <= 3'd1; ptimer <= 2'd2;
        end
      end

      // basemul pass sequencer
      if (!job_start && op_r == BM && pass != 3'd0) begin
        if (ptimer != 2'd0) ptimer <= ptimer - 2'd1;
        else begin
          if (pass == 3'd2) piece <= piece + 7'd1;
          pass   <= (pass == 3'd4) ? 3'd0 : pass + 3'd1;
          ptimer <= 2'd2;
        end
      end

      // results
      if (!job_start) begin
        inv_d <= {inv_d[0], take && op_r == INV && idx[0]};
        if (inv_d[1]) opr3 <= opr2;
        pair_pend <= bm_res && res_idx == 3'd4;
        if (bm_res) res_idx <= (res_idx == 3'd4) ? 3'd0 : res_idx + 3'd1;
        if (p_valid && op_r == SC) begin
          sc_odd <= ~sc_odd;
          if (!sc_odd) opr0 <= p_out;
        end
      end
    end
  end

  // ---------------- result pair ----------------
  always @(*) begin
    case (op_r)
      FWD:     begin pair_valid = p_valid;            r0 = post_sum; r1 = post_diff; end
      INV:     begin pair_valid = p_valid;            r0 = opr3;       r1 = p_out;     end
      BM:      begin pair_valid = pair_pend;          r0 = acc0;     r1 = acc1;      end
      default: begin pair_valid = p_valid && sc_odd;  r0 = opr0;       r1 = p_out;     end
    endcase
  end

  wire _unused = &{m_ready, 1'b0};
endmodule
