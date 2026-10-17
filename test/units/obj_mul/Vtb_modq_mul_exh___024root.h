// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_modq_mul_exh.h for the primary calling header

#ifndef VERILATED_VTB_MODQ_MUL_EXH___024ROOT_H_
#define VERILATED_VTB_MODQ_MUL_EXH___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_modq_mul_exh__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_modq_mul_exh___024root final {
  public:

    // DESIGN-SPECIFIC STATE
    CData/*0:0*/ tb_modq_mul_exh__DOT__clk;
    CData/*0:0*/ tb_modq_mul_exh__DOT__rst_n;
    CData/*0:0*/ tb_modq_mul_exh__DOT__start;
    CData/*0:0*/ tb_modq_mul_exh__DOT__p_valid;
    CData/*7:0*/ tb_modq_mul_exh__DOT__dut__DOT__rb_hi;
    CData/*1:0*/ tb_modq_mul_exh__DOT__dut__DOT__phase;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0;
    SData/*11:0*/ tb_modq_mul_exh__DOT__a_in;
    SData/*11:0*/ tb_modq_mul_exh__DOT__b_in;
    SData/*11:0*/ tb_modq_mul_exh__DOT__p_out;
    SData/*11:0*/ tb_modq_mul_exh__DOT__dut__DOT__ra;
    SData/*15:0*/ tb_modq_mul_exh__DOT__dut__DOT__pp;
    SData/*14:0*/ tb_modq_mul_exh__DOT__dut__DOT__r2;
    IData/*31:0*/ tb_modq_mul_exh__DOT__b;
    IData/*31:0*/ tb_modq_mul_exh__DOT__errors;
    IData/*31:0*/ tb_modq_mul_exh__DOT__cyc;
    IData/*31:0*/ tb_modq_mul_exh__DOT__head;
    IData/*31:0*/ tb_modq_mul_exh__DOT__tail;
    IData/*23:0*/ tb_modq_mul_exh__DOT__dut__DOT__acc;
    IData/*31:0*/ __Vi;
    VlUnpacked<SData/*11:0*/, 8> tb_modq_mul_exh__DOT__exp_q;
    VlUnpacked<QData/*63:0*/, 8> tb_modq_mul_exh__DOT__start_cyc;
    VlUnpacked<QData/*63:0*/, 1> __VstlTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VicoTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VactTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VactTriggeredAcc;
    VlUnpacked<QData/*63:0*/, 1> __VnbaTriggered;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h0dbf2f95__0;

    // INTERNAL VARIABLES
    Vtb_modq_mul_exh__Syms* vlSymsp;
    const char* vlNamep;

    // CONSTRUCTORS
    Vtb_modq_mul_exh___024root(Vtb_modq_mul_exh__Syms* symsp, const char* namep);
    ~Vtb_modq_mul_exh___024root();
    VL_UNCOPYABLE(Vtb_modq_mul_exh___024root);

    // INTERNAL METHODS
};


#endif  // guard
