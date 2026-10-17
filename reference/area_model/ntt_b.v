// Design B: 16-coefficient block engine + A's streaming mode as fallback.
// Header word at sof: [2] block mode, [1:0] pass (0 fwd strided, 1 fwd contiguous,
// 2 inv contiguous, 3 inv strided), [6:3] block index, [7] shuffle enable.
module tt_um_ntt_b #(parameter SERIAL = 1) (
    input  wire [7:0] ui_in, output wire [7:0] uo_out,
    input  wire [7:0] uio_in, output wire [7:0] uio_out, output wire [7:0] uio_oe,
    input  wire ena, clk, rst_n
);
    `include "zeta_rom.vh"
    wire [11:0] din = {uio_in[3:0], ui_in};
    wire valid = uio_in[4], sof = uio_in[5];
    wire [1:0] op = uio_in[7:6];

    // ---------------- streaming path (identical to A) ----------------
    reg [6:0] bf; reg [2:0] layer; reg [6:0] pair;
    reg [11:0] w0, w1, w2; reg [1:0] wcnt; reg [1:0] sop;
    wire [1:0] need = (op == 2'd2) ? 2'd3 : 2'd1;
    wire [6:0] zf = (7'd1 << layer) + (bf >> (3'd7 - layer));
    wire [6:0] zi = (7'd127 >> layer) - (bf >> (layer + 3'd1));
    wire [6:0] sidx = (op == 2'd0) ? zf : (op == 2'd1) ? zi : (7'd64 + pair[6:1]);
    reg s_start; reg [11:0] sx0, sx1, sy0, sy1, sz;
    wire [11:0] zr, zsel;

    // ---------------- block engine (B only) ----------------
    reg        blk_mode, shuf_en;
    reg [1:0]  pass;
    reg [3:0]  blk;
    reg [11:0] buf_r [0:15];
    reg [1:0]  phase;            // 0 load, 1 compute, 2 unload, 3 idle
    reg [3:0]  lcnt;             // load / unload counter
    reg [1:0]  ll;               // local layer
    reg [2:0]  k;                // butterfly within layer
    reg [2:0]  mask;
    reg [15:0] lfsr;
    reg        b_start, b_wait;
    wire       pk_busy; reg pk_ld;

    wire [2:0] nlay  = (pass == 2'd0 || pass == 2'd3) ? 3'd4 : 3'd3;
    wire       inv   = pass[1];
    // local stride (log2): fwd strided 3,2,1,0 ; fwd contig 3,2,1 ; inv contig 1,2,3 ; inv strided 0,1,2,3
    wire [1:0] ls = (pass == 2'd0) ? (2'd3 - ll) : (pass == 2'd1) ? (2'd3 - ll) :
                    (pass == 2'd2) ? (ll + 2'd1) : ll;
    wire [2:0] kk = k ^ mask;                          // shuffled butterfly order
    wire [3:0] stride = 4'd1 << ls;
    wire [3:0] ii = (({1'b0, kk} >> ls) << (ls + 1)) | ({1'b0, kk} & (stride - 4'd1));
    wire [3:0] jj = ii + stride;
    // twiddle index (verified schedule, see mlkem_ntt_model.py)
    wire [7:0] gc  = {blk, ii};                        // global index, contiguous passes
    wire [6:0] zb_f1 = (7'd1 << ll) + (ii >> (3'd4 - ll));
    wire [6:0] zb_f2 = (7'd16 << ll) + (gc >> (3'd4 - ll));
    wire [6:0] zb_i1 = (7'd127 >> ll) - (gc >> (ll + 3'd2));
    wire [6:0] zb_i2 = (7'd15 >> ll) - (ii >> (ll + 3'd1));
    wire [6:0] zb = (pass == 2'd0) ? zb_f1 : (pass == 2'd1) ? zb_f2 : (pass == 2'd2) ? zb_i1 : zb_i2;

    assign zr = zeta_rom(blk_mode ? zb : sidx);       // ONE shared twiddle ROM
    assign zsel = (op[1] && pair[0]) ? (12'd3329 - zr) : zr;
    // shared processing element, operands from stream path or buffer
    wire pdone; wire [11:0] o0, o1;
    wire use_blk = blk_mode;
    pe #(.SERIAL(SERIAL)) u_pe (.clk(clk), .rst_n(rst_n),
        .start(use_blk ? b_start : s_start),
        .op(use_blk ? {1'b0, inv} : sop),
        .x0(use_blk ? buf_r[ii] : sx0), .x1(use_blk ? buf_r[jj] : sx1),
        .y0(sy0), .y1(sy1),
        .z(use_blk ? zr : sz),
        .done(pdone), .o0(o0), .o1(o1));

    integer n;
    always @(posedge clk) begin
        if (!rst_n) begin
            bf <= 0; layer <= 0; pair <= 0; wcnt <= 0; s_start <= 0; sop <= 0;
            w0 <= 0; w1 <= 0; w2 <= 0; sx0 <= 0; sx1 <= 0; sy0 <= 0; sy1 <= 0; sz <= 0;
            blk_mode <= 0; shuf_en <= 0; pass <= 0; blk <= 0; phase <= 2'd3; lcnt <= 0;
            ll <= 0; k <= 0; mask <= 0; lfsr <= 16'hACE1; b_start <= 0; b_wait <= 0;
            for (n = 0; n < 16; n = n + 1) buf_r[n] <= 12'd0;
        end else begin
            s_start <= 1'b0; b_start <= 1'b0;
            lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
            if (sof) begin
                bf <= 0; layer <= 0; pair <= 0; wcnt <= 0;
                blk_mode <= din[2]; pass <= din[1:0]; blk <= din[6:3]; shuf_en <= din[7];
                phase <= 2'd0; lcnt <= 0;
            end else if (!blk_mode) begin
                if (valid) begin
                    if (wcnt == need) begin
                        sop <= op; sz <= zsel; s_start <= 1'b1; wcnt <= 0;
                        if (op == 2'd2) begin sx0 <= w0; sx1 <= w1; sy0 <= w2; sy1 <= din; pair <= pair + 7'd1; end
                        else begin sx0 <= w0; sx1 <= din; end
                        if (op[1] == 1'b0) begin bf <= bf + 7'd1; if (bf == 7'd127) layer <= layer + 3'd1; end
                    end else begin
                        case (wcnt) 2'd0: w0 <= din; 2'd1: w1 <= din; default: w2 <= din; endcase
                        wcnt <= wcnt + 2'd1;
                    end
                end
            end else begin
                case (phase)
                    2'd0: if (valid) begin            // load 16 coefficients
                        buf_r[lcnt] <= din; lcnt <= lcnt + 4'd1;
                        if (lcnt == 4'd15) begin phase <= 2'd1; ll <= 0; k <= 0; mask <= shuf_en ? lfsr[2:0] : 3'd0; b_start <= 1'b1; b_wait <= 1'b1; end
                    end
                    2'd1: if (pdone) begin            // write back, next butterfly
                        buf_r[ii] <= o0; buf_r[jj] <= o1;
                        if (k == 3'd7) begin
                            k <= 0; mask <= shuf_en ? lfsr[5:3] : 3'd0;
                            if ({1'b0, ll} == nlay - 3'd1) begin phase <= 2'd2; lcnt <= 0; b_wait <= 0; end
                            else begin ll <= ll + 2'd1; b_start <= 1'b1; end
                        end else begin k <= k + 3'd1; b_start <= 1'b1; end
                    end
                    2'd2: if (!pk_busy && !pk_ld) begin  // unload pairs through packer
                        lcnt <= lcnt + 4'd2;
                        if (lcnt == 4'd14) phase <= 2'd3;
                    end
                    default: ;
                endcase
            end
        end
    end

    wire unload = blk_mode && (phase == 2'd2);

    always @(posedge clk) pk_ld <= !rst_n ? 1'b0 : (unload && !pk_busy && !pk_ld);
    packer u_pk (.clk(clk), .rst_n(rst_n),
        .load(unload ? (!pk_busy && !pk_ld) : (!blk_mode && pdone)),
        .v0(unload ? buf_r[lcnt] : o0), .v1(unload ? buf_r[lcnt + 4'd1] : o1),
        .dout(uo_out), .busy(pk_busy));
    assign uio_out = 8'h00;
    assign uio_oe  = 8'h00;
endmodule
