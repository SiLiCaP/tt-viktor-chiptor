// Design A (friend's): butterfly stream. No coefficient storage.
// Pins: din = {uio_in[3:0], ui_in}, valid = uio_in[4], sof = uio_in[5], op = uio_in[7:6]
module tt_um_ntt_a #(parameter SERIAL = 1) (
    input  wire [7:0] ui_in, output wire [7:0] uo_out,
    input  wire [7:0] uio_in, output wire [7:0] uio_out, output wire [7:0] uio_oe,
    input  wire ena, clk, rst_n
);
    `include "zeta_rom.vh"
    wire [11:0] din = {uio_in[3:0], ui_in};
    wire valid = uio_in[4], sof = uio_in[5];
    wire [1:0] op = uio_in[7:6];

    // sequencer: butterfly and layer counters -> twiddle index
    reg [6:0] bf; reg [2:0] layer; reg [6:0] pair;
    reg [11:0] w0, w1, w2; reg [1:0] wcnt; reg [1:0] rop;
    wire [1:0] need = (op == 2'd2) ? 2'd3 : 2'd1;   // basemul takes 4 words
    wire [6:0] zf = (7'd1 << layer) + (bf >> (3'd7 - layer));
    wire [6:0] zi = (7'd127 >> layer) - (bf >> (layer + 3'd1));
    wire [6:0] sidx = (op == 2'd0) ? zf : (op == 2'd1) ? zi : (7'd64 + pair[6:1]);

    wire [11:0] zr = zeta_rom(sidx);                  // ONE shared twiddle ROM
    wire [11:0] zsel = (op[1] && pair[0]) ? (12'd3329 - zr) : zr;
    reg pstart; wire pdone; wire [11:0] o0, o1;
    reg [11:0] px0, px1, py0, py1, pz;
    pe #(.SERIAL(SERIAL)) u_pe (.clk(clk), .rst_n(rst_n), .start(pstart), .op(rop),
        .x0(px0), .x1(px1), .y0(py0), .y1(py1), .z(pz), .done(pdone), .o0(o0), .o1(o1));

    always @(posedge clk) begin
        if (!rst_n) begin
            bf <= 0; layer <= 0; pair <= 0; wcnt <= 0; pstart <= 0; rop <= 0;
            w0 <= 0; w1 <= 0; w2 <= 0; px0 <= 0; px1 <= 0; py0 <= 0; py1 <= 0; pz <= 0;
        end else begin
            pstart <= 1'b0;
            if (sof) begin bf <= 0; layer <= 0; pair <= 0; wcnt <= 0; end
            if (valid) begin
                if (wcnt == need) begin
                    // last operand word arrived: launch the processing element
                    rop <= op; pz <= zsel; pstart <= 1'b1; wcnt <= 0;
                    if (op == 2'd2) begin px0 <= w0; px1 <= w1; py0 <= w2; py1 <= din; pair <= pair + 7'd1; end
                    else begin px0 <= w0; px1 <= din; end
                    if (op[1] == 1'b0) begin
                        bf <= bf + 7'd1;
                        if (bf == 7'd127) layer <= layer + 3'd1;
                    end
                end else begin
                    case (wcnt) 2'd0: w0 <= din; 2'd1: w1 <= din; default: w2 <= din; endcase
                    wcnt <= wcnt + 2'd1;
                end
            end
        end
    end

    packer u_pk (.clk(clk), .rst_n(rst_n), .load(pdone), .v0(o0), .v1(o1), .dout(uo_out), .busy());
    assign uio_out = 8'h00;
    assign uio_oe  = 8'h00;
endmodule
