// Shared arithmetic core for both designs (area model).
// q = 3329. Barrett: t = (x*5039)>>24, r = x - t*q, <=2 conditional subtracts.
`define Q 12'd3329

module mulmod #(parameter SERIAL = 1) (
    input  wire        clk, rst_n,
    input  wire        start,
    input  wire [11:0] a, b,
    output wire        done,
    output wire [11:0] r
);
    function [11:0] barrett; input [23:0] x;
        reg [36:0] t1; reg [12:0] t; reg [24:0] rr;
        begin
            t1 = x * 13'd5039;
            t  = t1[36:24];
            rr = {1'b0, x} - t * 12'd3329;
            if (rr >= 25'd3329) rr = rr - 25'd3329;
            if (rr >= 25'd3329) rr = rr - 25'd3329;
            barrett = rr[11:0];
        end
    endfunction

    generate if (SERIAL) begin : g_serial
        // 4-bit digit-serial: 3 clocks per 12x12 product, MSB digit first
        reg [23:0] acc; reg [1:0] cnt; reg busy, dn;
        reg [11:0] ra, rb;
        wire [3:0] dig = (cnt == 2'd0) ? rb[11:8] : (cnt == 2'd1) ? rb[7:4] : rb[3:0];
        always @(posedge clk) begin
            if (!rst_n) begin acc <= 0; cnt <= 0; busy <= 0; dn <= 0; ra <= 0; rb <= 0; end
            else begin
                dn <= 1'b0;
                if (start && !busy) begin ra <= a; rb <= b; acc <= 0; cnt <= 0; busy <= 1'b1; end
                else if (busy) begin
                    acc <= {acc[19:0], 4'b0} + ra * dig;
                    cnt <= cnt + 2'd1;
                    if (cnt == 2'd2) begin busy <= 1'b0; dn <= 1'b1; end
                end
            end
        end
        assign done = dn;
        assign r = barrett(acc);
    end else begin : g_par
        // full parallel 12x12 + Barrett, combinational (1 product per clock)
        assign done = start;
        assign r = barrett(a * b);
    end endgenerate
endmodule

// Processing element: CT / GS butterfly, basemul, scale. One multiplier.
module pe #(parameter SERIAL = 1) (
    input  wire        clk, rst_n,
    input  wire        start,
    input  wire [1:0]  op,          // 0 CT, 1 GS, 2 basemul, 3 scale
    input  wire [11:0] x0, x1, y0, y1, z,
    output reg         done,
    output reg  [11:0] o0, o1
);
    function [11:0] addq; input [11:0] p, s; reg [12:0] v;
        begin v = p + s; if (v >= 13'd3329) v = v - 13'd3329; addq = v[11:0]; end endfunction
    function [11:0] subq; input [11:0] p, s; reg [12:0] v;
        begin v = {1'b0,p} + 13'd3329 - s; if (v >= 13'd3329) v = v - 13'd3329; subq = v[11:0]; end endfunction

    reg [1:0]  rop; reg [2:0] step; reg run, mstart;
    reg [11:0] rx0, rx1, ry0, ry1, rz, tmp;
    reg [11:0] ma, mb;
    wire mdone; wire [11:0] mr;
    mulmod #(.SERIAL(SERIAL)) u_mul (.clk(clk), .rst_n(rst_n), .start(mstart), .a(ma), .b(mb), .done(mdone), .r(mr));

    reg [2:0] last;
    always @* begin
        ma = rx1; mb = rz; last = 3'd0;
        case (rop)
            2'd0: begin ma = rx1; mb = rz; last = 3'd0; end
            2'd1: begin ma = subq(rx1, rx0); mb = rz; last = 3'd0; end
            2'd3: begin ma = step[0] ? rx1 : rx0; mb = 12'd3303; last = 3'd1; end
            2'd2: begin
                last = 3'd4;
                case (step)
                    3'd0: begin ma = rx1; mb = ry1; end
                    3'd1: begin ma = tmp; mb = rz;  end
                    3'd2: begin ma = rx0; mb = ry0; end
                    3'd3: begin ma = rx0; mb = ry1; end
                    default: begin ma = rx1; mb = ry0; end
                endcase
            end
        endcase
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            run <= 0; mstart <= 0; done <= 0; step <= 0; rop <= 0;
            rx0 <= 0; rx1 <= 0; ry0 <= 0; ry1 <= 0; rz <= 0; tmp <= 0; o0 <= 0; o1 <= 0;
        end else begin
            done <= 1'b0;
            mstart <= 1'b0;
            if (start && !run) begin
                rop <= op; rx0 <= x0; rx1 <= x1; ry0 <= y0; ry1 <= y1; rz <= z;
                step <= 0; run <= 1'b1; mstart <= 1'b1;
            end else if (run && mdone) begin
                case (rop)
                    2'd0: begin o0 <= addq(rx0, mr); o1 <= subq(rx0, mr); end
                    2'd1: begin o0 <= addq(rx0, rx1); o1 <= mr; end
                    2'd3: begin if (step[0]) o1 <= mr; else o0 <= mr; end
                    2'd2: case (step)
                        3'd0: tmp <= mr;
                        3'd1: o0 <= mr;
                        3'd2: o0 <= addq(o0, mr);
                        3'd3: o1 <= mr;
                        default: o1 <= addq(o1, mr);
                    endcase
                endcase
                if (step == last) begin run <= 1'b0; done <= 1'b1; end
                else begin step <= step + 3'd1; mstart <= 1'b1; end
            end
        end
    end
endmodule

// ByteEncode12 packer: two 12-bit values -> 3 bytes, one per clock
module packer (
    input  wire        clk, rst_n,
    input  wire        load,
    input  wire [11:0] v0, v1,
    output wire [7:0]  dout,
    output wire        busy
);
    reg [23:0] sh; reg [1:0] n;
    always @(posedge clk) begin
        if (!rst_n) begin sh <= 0; n <= 0; end
        else if (load) begin sh <= {v1, v0}; n <= 2'd3; end
        else if (n != 0) begin sh <= {8'b0, sh[23:8]}; n <= n - 2'd1; end
    end
    assign dout = sh[7:0];
    assign busy = (n != 0);
endmodule
