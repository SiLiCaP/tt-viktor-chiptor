// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_modq_mul_exh.h for the primary calling header

#include "Vtb_modq_mul_exh__pch.h"

VlCoroutine Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__0(Vtb_modq_mul_exh___024root* vlSelf);
VlCoroutine Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__1(Vtb_modq_mul_exh___024root* vlSelf);

void Vtb_modq_mul_exh___024root___eval_initial(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_initial\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__1(vlSelf);
}

void Vtb_modq_mul_exh___024root___eval_sample(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_sample\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

bool Vtb_modq_mul_exh___024root___eval_ico(Vtb_modq_mul_exh___024root* vlSelf, CData/*0:0*/ firstIteration) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_ico\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VicoTriggered[0U] = ((0xfffffffffffffffeULL 
                                      & vlSelfRef.__VicoTriggered[0U]) 
                                     | (IData)((IData)(firstIteration)));
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_modq_mul_exh___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
    }
#endif
    return (0U);
}

void Vtb_modq_mul_exh___024root___timing_ready(Vtb_modq_mul_exh___024root* vlSelf);
void Vtb_modq_mul_exh___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in);
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG
bool Vtb_modq_mul_exh___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in);
void Vtb_modq_mul_exh___024root___timing_resume(Vtb_modq_mul_exh___024root* vlSelf);

bool Vtb_modq_mul_exh___024root___eval_act(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_act\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VactExecute;
    // Body
    {
        // Inlined CFunc: _eval_triggers_vec__act
        vlSelfRef.__VactTriggered[0U] = (QData)((IData)(
                                                        ((vlSelfRef.__VdlySched.awaitingCurrentTime() 
                                                          << 2U) 
                                                         | ((((~ (IData)(vlSelfRef.tb_modq_mul_exh__DOT__clk)) 
                                                              & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0)) 
                                                             << 1U) 
                                                            | ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__clk) 
                                                               & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0)))))));
        vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0 
            = vlSelfRef.tb_modq_mul_exh__DOT__clk;
    }
    Vtb_modq_mul_exh___024root___timing_ready(vlSelf);
    Vtb_modq_mul_exh___024root___trigger_orInto__act_vec_vec(vlSelfRef.__VactTriggered, vlSelfRef.__VactTriggeredAcc);
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_modq_mul_exh___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
    }
#endif
    Vtb_modq_mul_exh___024root___trigger_orInto__act_vec_vec(vlSelfRef.__VnbaTriggered, vlSelfRef.__VactTriggered);
    __VactExecute = Vtb_modq_mul_exh___024root___trigger_anySet__act(vlSelfRef.__VactTriggered);
    if (__VactExecute) {
        vlSelfRef.__VactTriggeredAcc.fill(0ULL);
        Vtb_modq_mul_exh___024root___timing_resume(vlSelf);
    }
    return (__VactExecute);
}

bool Vtb_modq_mul_exh___024root___eval_inact(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_inact\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VinactExecute;
    // Body
    __VinactExecute = vlSelfRef.__VdlySched.awaitingZeroDelay();
    if (__VinactExecute) {
        VL_FATAL_MT("tb_modq_mul_exh.v", 5, "", "ZERODLY: Design Verilated with '--no-sched-zero-delay', but #0 delay executed at runtime");
    }
    return (__VinactExecute);
}

void Vtb_modq_mul_exh___024root___nba_sequent__TOP__0(Vtb_modq_mul_exh___024root* vlSelf);
void Vtb_modq_mul_exh___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out);

bool Vtb_modq_mul_exh___024root___eval_nba(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_nba\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = Vtb_modq_mul_exh___024root___trigger_anySet__act(vlSelfRef.__VnbaTriggered);
    if (__VnbaExecute) {
        {
            // Inlined CFunc: _eval_body__nba
            if ((1ULL & vlSelfRef.__VnbaTriggered[0U])) {
                Vtb_modq_mul_exh___024root___nba_sequent__TOP__0(vlSelf);
            }
        }
        Vtb_modq_mul_exh___024root___trigger_clear__act(vlSelfRef.__VnbaTriggered);
    }
    return (__VnbaExecute);
}

bool Vtb_modq_mul_exh___024root___eval_obs(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_obs\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

bool Vtb_modq_mul_exh___024root___eval_react(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_react\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

void Vtb_modq_mul_exh___024root___eval_postponed(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_postponed\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(Vtb_modq_mul_exh___024root* vlSelf, const char* __VeventDescription);

VlCoroutine Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__0(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__0\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ tb_modq_mul_exh__DOT__a;
    tb_modq_mul_exh__DOT__a = 0;
    IData/*31:0*/ tb_modq_mul_exh__DOT__unnamedblk1_1__DOT____Vrepeat0;
    tb_modq_mul_exh__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    IData/*31:0*/ tb_modq_mul_exh__DOT__unnamedblk1_2__DOT____Vrepeat1;
    tb_modq_mul_exh__DOT__unnamedblk1_2__DOT____Vrepeat1 = 0;
    // Body
    tb_modq_mul_exh__DOT__unnamedblk1_1__DOT____Vrepeat0 = 3U;
    while (VL_LTS_III(32, 0U, tb_modq_mul_exh__DOT__unnamedblk1_1__DOT____Vrepeat0)) {
        Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(vlSelf, 
                                                               "@(negedge tb_modq_mul_exh.clk)");
        co_await vlSelfRef.__VtrigSched_h0dbf2f95__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(negedge tb_modq_mul_exh.clk)", 
                                                             "tb_modq_mul_exh.v", 
                                                             32);
        tb_modq_mul_exh__DOT__unnamedblk1_1__DOT____Vrepeat0 
            = (tb_modq_mul_exh__DOT__unnamedblk1_1__DOT____Vrepeat0 
               - (IData)(1U));
    }
    vlSelfRef.tb_modq_mul_exh__DOT__rst_n = 1U;
    tb_modq_mul_exh__DOT__a = 0U;
    while (VL_GTS_III(32, 0x00000d01U, tb_modq_mul_exh__DOT__a)) {
        vlSelfRef.tb_modq_mul_exh__DOT__b = 0U;
        while (VL_GTS_III(32, 0x00000d01U, vlSelfRef.tb_modq_mul_exh__DOT__b)) {
            Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(vlSelf, 
                                                                   "@(negedge tb_modq_mul_exh.clk)");
            co_await vlSelfRef.__VtrigSched_h0dbf2f95__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(negedge tb_modq_mul_exh.clk)", 
                                                                 "tb_modq_mul_exh.v", 
                                                                 36);
            if (VL_UNLIKELY(((1U & (~ ((0U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase)) 
                                       | (3U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase)))))))) {
                VL_WRITEF_NX("ready low when a start is due\n",0);
                vlSelfRef.tb_modq_mul_exh__DOT__errors 
                    = ((IData)(1U) + vlSelfRef.tb_modq_mul_exh__DOT__errors);
            }
            vlSelfRef.tb_modq_mul_exh__DOT__start = 1U;
            vlSelfRef.tb_modq_mul_exh__DOT__a_in = 
                (0x00000fffU & tb_modq_mul_exh__DOT__a);
            vlSelfRef.tb_modq_mul_exh__DOT__b_in = 
                (0x00000fffU & vlSelfRef.tb_modq_mul_exh__DOT__b);
            vlSelfRef.tb_modq_mul_exh__DOT__exp_q[(7U 
                                                   & VL_MODDIVS_III(32, vlSelfRef.tb_modq_mul_exh__DOT__tail, (IData)(8U)))] 
                = (0x00000fffU & (IData)(VL_MODDIV_QQQ(64, 
                                                       (0x00000000000000a9ULL 
                                                        * 
                                                        ((QData)((IData)(tb_modq_mul_exh__DOT__a)) 
                                                         * (QData)((IData)(vlSelfRef.tb_modq_mul_exh__DOT__b)))), 0x0000000000000d01ULL)));
            vlSelfRef.tb_modq_mul_exh__DOT__start_cyc[(7U 
                                                       & VL_MODDIVS_III(32, vlSelfRef.tb_modq_mul_exh__DOT__tail, (IData)(8U)))] 
                = VL_EXTENDS_QI(64,32, vlSelfRef.tb_modq_mul_exh__DOT__cyc);
            vlSelfRef.tb_modq_mul_exh__DOT__tail = 
                ((IData)(1U) + vlSelfRef.tb_modq_mul_exh__DOT__tail);
            Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(vlSelf, 
                                                                   "@(negedge tb_modq_mul_exh.clk)");
            co_await vlSelfRef.__VtrigSched_h0dbf2f95__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(negedge tb_modq_mul_exh.clk)", 
                                                                 "tb_modq_mul_exh.v", 
                                                                 42);
            vlSelfRef.tb_modq_mul_exh__DOT__start = 0U;
            Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(vlSelf, 
                                                                   "@(negedge tb_modq_mul_exh.clk)");
            co_await vlSelfRef.__VtrigSched_h0dbf2f95__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(negedge tb_modq_mul_exh.clk)", 
                                                                 "tb_modq_mul_exh.v", 
                                                                 43);
            vlSelfRef.tb_modq_mul_exh__DOT__b = ((IData)(1U) 
                                                 + vlSelfRef.tb_modq_mul_exh__DOT__b);
        }
        tb_modq_mul_exh__DOT__a = ((IData)(1U) + tb_modq_mul_exh__DOT__a);
    }
    tb_modq_mul_exh__DOT__unnamedblk1_2__DOT____Vrepeat1 = 8U;
    while (VL_LTS_III(32, 0U, tb_modq_mul_exh__DOT__unnamedblk1_2__DOT____Vrepeat1)) {
        Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(vlSelf, 
                                                               "@(negedge tb_modq_mul_exh.clk)");
        co_await vlSelfRef.__VtrigSched_h0dbf2f95__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(negedge tb_modq_mul_exh.clk)", 
                                                             "tb_modq_mul_exh.v", 
                                                             46);
        tb_modq_mul_exh__DOT__unnamedblk1_2__DOT____Vrepeat1 
            = (tb_modq_mul_exh__DOT__unnamedblk1_2__DOT____Vrepeat1 
               - (IData)(1U));
    }
    if (VL_UNLIKELY(((vlSelfRef.tb_modq_mul_exh__DOT__head 
                      != vlSelfRef.tb_modq_mul_exh__DOT__tail)))) {
        VL_WRITEF_NX("lost results: %0d of %0d\n",2
                     , '~',32,vlSelfRef.tb_modq_mul_exh__DOT__head
                     , '~',32,vlSelfRef.tb_modq_mul_exh__DOT__tail);
        vlSelfRef.tb_modq_mul_exh__DOT__errors = ((IData)(1U) 
                                                  + vlSelfRef.tb_modq_mul_exh__DOT__errors);
    }
    if ((0U == vlSelfRef.tb_modq_mul_exh__DOT__errors)) {
        VL_WRITEF_NX("PASS: %0d products, latency 4, one start per 3 clocks\n",1
                     , '~',32,vlSelfRef.tb_modq_mul_exh__DOT__tail);
    } else {
        VL_WRITEF_NX("FAIL: %0d errors\n",1, '~',32,vlSelfRef.tb_modq_mul_exh__DOT__errors);
    }
    VL_FINISH_MT("tb_modq_mul_exh.v", 50, "");
    co_return;
}

VlCoroutine Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__1(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_initial__TOP__Vtiming__1\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (VL_LIKELY(!vlSymsp->_vm_contextp__->gotFinish())) {
        co_await vlSelfRef.__VdlySched.delay(0x0000000000001388ULL, 
                                             nullptr, 
                                             "tb_modq_mul_exh.v", 
                                             11);
        vlSelfRef.tb_modq_mul_exh__DOT__clk = (1U & 
                                               (~ (IData)(vlSelfRef.tb_modq_mul_exh__DOT__clk)));
    }
    co_return;
}

bool Vtb_modq_mul_exh___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___trigger_anySet__ico\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        if (in[n]) {
            return (1U);
        }
        n = ((IData)(1U) + n);
    } while ((1U > n));
    return (0U);
}

bool Vtb_modq_mul_exh___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___trigger_anySet__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        if (in[n]) {
            return (1U);
        }
        n = ((IData)(1U) + n);
    } while ((1U > n));
    return (0U);
}

void Vtb_modq_mul_exh___024root___nba_sequent__TOP__0(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___nba_sequent__TOP__0\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*17:0*/ tb_modq_mul_exh__DOT__dut__DOT__r1;
    tb_modq_mul_exh__DOT__dut__DOT__r1 = 0;
    IData/*23:0*/ __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc;
    __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc = 0;
    CData/*1:0*/ __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase;
    __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase = 0;
    // Body
    __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase = vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase;
    __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc = vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc;
    if (vlSelfRef.tb_modq_mul_exh__DOT__p_valid) {
        if ((((IData)(vlSelfRef.tb_modq_mul_exh__DOT__p_out) 
              != vlSelfRef.tb_modq_mul_exh__DOT__exp_q
              [(7U & VL_MODDIVS_III(32, vlSelfRef.tb_modq_mul_exh__DOT__head, (IData)(8U)))]) 
             | ((QData)((IData)(vlSelfRef.tb_modq_mul_exh__DOT__cyc)) 
                != (4ULL + vlSelfRef.tb_modq_mul_exh__DOT__start_cyc
                    [(7U & VL_MODDIVS_III(32, vlSelfRef.tb_modq_mul_exh__DOT__head, (IData)(8U)))])))) {
            vlSelfRef.tb_modq_mul_exh__DOT__errors 
                = ((IData)(1U) + vlSelfRef.tb_modq_mul_exh__DOT__errors);
            if (VL_UNLIKELY((VL_GTS_III(32, 0x0000000aU, vlSelfRef.tb_modq_mul_exh__DOT__errors)))) {
                VL_WRITEF_NX("MISMATCH start#%0d: got %0d at +%0d, expected %0d at +4\n",4
                             , '~',32,vlSelfRef.tb_modq_mul_exh__DOT__head
                             , '#',12,(IData)(vlSelfRef.tb_modq_mul_exh__DOT__p_out)
                             , '#',64,((QData)((IData)(vlSelfRef.tb_modq_mul_exh__DOT__cyc)) 
                                       - vlSelfRef.tb_modq_mul_exh__DOT__start_cyc
                                       [(7U & VL_MODDIVS_III(32, vlSelfRef.tb_modq_mul_exh__DOT__head, (IData)(8U)))])
                             , '#',12,vlSelfRef.tb_modq_mul_exh__DOT__exp_q
                             [(7U & VL_MODDIVS_III(32, vlSelfRef.tb_modq_mul_exh__DOT__head, (IData)(8U)))]);
            }
        }
        vlSelfRef.tb_modq_mul_exh__DOT__head = ((IData)(1U) 
                                                + vlSelfRef.tb_modq_mul_exh__DOT__head);
    }
    vlSelfRef.tb_modq_mul_exh__DOT__cyc = ((IData)(1U) 
                                           + vlSelfRef.tb_modq_mul_exh__DOT__cyc);
    if (vlSelfRef.tb_modq_mul_exh__DOT__rst_n) {
        if (vlSelfRef.tb_modq_mul_exh__DOT__start) {
            __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase = 1U;
            __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc 
                = (0x0000ffffU & ((0x0000000fU & (IData)(vlSelfRef.tb_modq_mul_exh__DOT__b_in)) 
                                  * (IData)(vlSelfRef.tb_modq_mul_exh__DOT__a_in)));
            vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__ra 
                = vlSelfRef.tb_modq_mul_exh__DOT__a_in;
            vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__rb_hi 
                = (0x000000ffU & ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__b_in) 
                                  >> 4U));
        } else if (((1U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase)) 
                    | (2U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase)))) {
            __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase 
                = (3U & ((IData)(1U) + (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase)));
            __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc 
                = (0x00ffffffU & (vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc 
                                  + (((1U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase))
                                       ? (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__pp)
                                       : ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__pp) 
                                          << 4U)) << 4U)));
        } else {
            __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase = 0U;
        }
        if ((3U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase))) {
            vlSelfRef.tb_modq_mul_exh__DOT__p_out = 
                (0x00000fffU & ((0x00004000U & (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2))
                                 ? ((IData)(0x0d01U) 
                                    + (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2))
                                 : ((0x00004000U & 
                                     ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2) 
                                      - (IData)(0x0d01U)))
                                     ? (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2)
                                     : ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2) 
                                        - (IData)(0x0d01U)))));
        }
    } else {
        __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase = 0U;
        __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__ra = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__rb_hi = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__p_out = 0U;
    }
    vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc = __Vdly__tb_modq_mul_exh__DOT__dut__DOT__acc;
    vlSelfRef.tb_modq_mul_exh__DOT__p_valid = ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__rst_n) 
                                               && (3U 
                                                   == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase)));
    tb_modq_mul_exh__DOT__dut__DOT__r1 = (0x0003ffffU 
                                          & ((0x00000fffU 
                                              & ((IData)(0x000dU) 
                                                 * 
                                                 (0x000000ffU 
                                                  & vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc))) 
                                             - (0x0000ffffU 
                                                & (vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc 
                                                   >> 8U))));
    vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase 
        = __Vdly__tb_modq_mul_exh__DOT__dut__DOT__phase;
    vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2 = 
        (0x00007fffU & ((0x00000fffU & ((IData)(0x000dU) 
                                        * (0x000000ffU 
                                           & tb_modq_mul_exh__DOT__dut__DOT__r1))) 
                        - ((0x00007c00U & ((- (IData)(
                                                      (1U 
                                                       & (tb_modq_mul_exh__DOT__dut__DOT__r1 
                                                          >> 0x00000011U)))) 
                                           << 0x0000000aU)) 
                           | (0x000003ffU & (tb_modq_mul_exh__DOT__dut__DOT__r1 
                                             >> 8U)))));
    vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__pp = 
        (0x0000ffffU & ((0x0000000fU & ((1U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase))
                                         ? (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__rb_hi)
                                         : ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__rb_hi) 
                                            >> 4U))) 
                        * (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__ra)));
}

void Vtb_modq_mul_exh___024root___timing_ready(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___timing_ready\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((2ULL & vlSelfRef.__VactTriggered[0U])) {
        vlSelfRef.__VtrigSched_h0dbf2f95__0.ready("@(negedge tb_modq_mul_exh.clk)");
    }
}

void Vtb_modq_mul_exh___024root___timing_resume(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___timing_resume\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VtrigSched_h0dbf2f95__0.moveToResumeQueue(
                                                          "@(negedge tb_modq_mul_exh.clk)");
    vlSelfRef.__VtrigSched_h0dbf2f95__0.resume("@(negedge tb_modq_mul_exh.clk)");
    if ((4ULL & vlSelfRef.__VactTriggered[0U])) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_modq_mul_exh___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___trigger_orInto__act_vec_vec\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = (out[n] | in[n]);
        n = ((IData)(1U) + n);
    } while ((0U >= n));
}

void Vtb_modq_mul_exh___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___trigger_clear__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = 0ULL;
        n = ((IData)(1U) + n);
    } while ((1U > n));
}

void Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0(Vtb_modq_mul_exh___024root* vlSelf, const char* __VeventDescription) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root____VbeforeTrig_h0dbf2f95__0\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    VlUnpacked<QData/*63:0*/, 1> __VTmp;
    // Body
    __VTmp[0U] = (QData)((IData)((((~ (IData)(vlSelfRef.tb_modq_mul_exh__DOT__clk)) 
                                   & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0)) 
                                  << 1U)));
    vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0 
        = vlSelfRef.tb_modq_mul_exh__DOT__clk;
    if ((2ULL & __VTmp[0U])) {
        vlSelfRef.__VtrigSched_h0dbf2f95__0.ready(__VeventDescription);
        vlSelfRef.__VtrigSched_h0dbf2f95__0.ready(__VeventDescription);
        vlSelfRef.__VtrigSched_h0dbf2f95__0.ready(__VeventDescription);
        vlSelfRef.__VtrigSched_h0dbf2f95__0.ready(__VeventDescription);
        vlSelfRef.__VtrigSched_h0dbf2f95__0.ready(__VeventDescription);
    }
    vlSelfRef.__VactTriggeredAcc[0U] = (vlSelfRef.__VactTriggeredAcc[0U] 
                                        | __VTmp[0U]);
}

#ifdef VL_DEBUG
void Vtb_modq_mul_exh___024root___eval_debug_assertions(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_debug_assertions\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
