// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb_modq_addsub_exh.h for the primary calling header

#ifndef VERILATED_VTB_MODQ_ADDSUB_EXH___024ROOT_H_
#define VERILATED_VTB_MODQ_ADDSUB_EXH___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb_modq_addsub_exh__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb_modq_addsub_exh___024root final {
  public:

    // DESIGN-SPECIFIC STATE
    CData/*0:0*/ tb_modq_addsub_exh__DOT__clk;
    CData/*0:0*/ tb_modq_addsub_exh__DOT__rst_n;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb_modq_addsub_exh__DOT__clk__0;
    SData/*11:0*/ tb_modq_addsub_exh__DOT__x;
    SData/*11:0*/ tb_modq_addsub_exh__DOT__y;
    SData/*11:0*/ tb_modq_addsub_exh__DOT__es;
    SData/*11:0*/ tb_modq_addsub_exh__DOT__ed;
    SData/*11:0*/ tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__sum_r;
    SData/*11:0*/ tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__diff_r;
    SData/*12:0*/ tb_modq_addsub_exh__DOT__u0__DOT__s;
    SData/*12:0*/ tb_modq_addsub_exh__DOT__u0__DOT__d;
    IData/*31:0*/ tb_modq_addsub_exh__DOT__j;
    IData/*31:0*/ tb_modq_addsub_exh__DOT__errors;
    IData/*31:0*/ __Vi;
    VlUnpacked<QData/*63:0*/, 1> __VstlTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VicoTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VactTriggered;
    VlUnpacked<QData/*63:0*/, 1> __VactTriggeredAcc;
    VlUnpacked<QData/*63:0*/, 1> __VnbaTriggered;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_hb0d7f014__0;

    // INTERNAL VARIABLES
    Vtb_modq_addsub_exh__Syms* vlSymsp;
    const char* vlNamep;

    // CONSTRUCTORS
    Vtb_modq_addsub_exh___024root(Vtb_modq_addsub_exh__Syms* symsp, const char* namep);
    ~Vtb_modq_addsub_exh___024root();
    VL_UNCOPYABLE(Vtb_modq_addsub_exh___024root);

    // INTERNAL METHODS
};


#endif  // guard
