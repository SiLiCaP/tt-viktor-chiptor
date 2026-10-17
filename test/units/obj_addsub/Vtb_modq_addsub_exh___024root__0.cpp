// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_modq_addsub_exh.h for the primary calling header

#include "Vtb_modq_addsub_exh__pch.h"

VlCoroutine Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__0(Vtb_modq_addsub_exh___024root* vlSelf);
VlCoroutine Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__1(Vtb_modq_addsub_exh___024root* vlSelf);

void Vtb_modq_addsub_exh___024root___eval_initial(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_initial\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__1(vlSelf);
}

void Vtb_modq_addsub_exh___024root___eval_sample(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_sample\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

bool Vtb_modq_addsub_exh___024root___eval_ico(Vtb_modq_addsub_exh___024root* vlSelf, CData/*0:0*/ firstIteration) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_ico\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VicoTriggered[0U] = ((0xfffffffffffffffeULL 
                                      & vlSelfRef.__VicoTriggered[0U]) 
                                     | (IData)((IData)(firstIteration)));
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_modq_addsub_exh___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
    }
#endif
    return (0U);
}

void Vtb_modq_addsub_exh___024root___timing_ready(Vtb_modq_addsub_exh___024root* vlSelf);
void Vtb_modq_addsub_exh___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in);
#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG
bool Vtb_modq_addsub_exh___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in);
void Vtb_modq_addsub_exh___024root___timing_resume(Vtb_modq_addsub_exh___024root* vlSelf);

bool Vtb_modq_addsub_exh___024root___eval_act(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_act\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VactExecute;
    // Body
    {
        // Inlined CFunc: _eval_triggers_vec__act
        vlSelfRef.__VactTriggered[0U] = (QData)((IData)(
                                                        ((vlSelfRef.__VdlySched.awaitingCurrentTime() 
                                                          << 2U) 
                                                         | ((((~ (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__clk)) 
                                                              & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_addsub_exh__DOT__clk__0)) 
                                                             << 1U) 
                                                            | ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__clk) 
                                                               & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_addsub_exh__DOT__clk__0)))))));
        vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_addsub_exh__DOT__clk__0 
            = vlSelfRef.tb_modq_addsub_exh__DOT__clk;
    }
    Vtb_modq_addsub_exh___024root___timing_ready(vlSelf);
    Vtb_modq_addsub_exh___024root___trigger_orInto__act_vec_vec(vlSelfRef.__VactTriggered, vlSelfRef.__VactTriggeredAcc);
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_modq_addsub_exh___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
    }
#endif
    Vtb_modq_addsub_exh___024root___trigger_orInto__act_vec_vec(vlSelfRef.__VnbaTriggered, vlSelfRef.__VactTriggered);
    __VactExecute = Vtb_modq_addsub_exh___024root___trigger_anySet__act(vlSelfRef.__VactTriggered);
    if (__VactExecute) {
        vlSelfRef.__VactTriggeredAcc.fill(0ULL);
        Vtb_modq_addsub_exh___024root___timing_resume(vlSelf);
        {
            // Inlined CFunc: _eval_body__act
            if ((6ULL & vlSelfRef.__VactTriggered[0U])) {
                {
                    // Inlined CFunc: _act_comb__TOP__0
                    vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s 
                        = (0x00001fffU & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__y) 
                                          + (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__x)));
                    vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d 
                        = (0x00001fffU & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__x) 
                                          - (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__y)));
                }
            }
        }
    }
    return (__VactExecute);
}

bool Vtb_modq_addsub_exh___024root___eval_inact(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_inact\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VinactExecute;
    // Body
    __VinactExecute = vlSelfRef.__VdlySched.awaitingZeroDelay();
    if (__VinactExecute) {
        VL_FATAL_MT("tb_modq_addsub_exh.v", 4, "", "ZERODLY: Design Verilated with '--no-sched-zero-delay', but #0 delay executed at runtime");
    }
    return (__VinactExecute);
}

void Vtb_modq_addsub_exh___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out);

bool Vtb_modq_addsub_exh___024root___eval_nba(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_nba\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = Vtb_modq_addsub_exh___024root___trigger_anySet__act(vlSelfRef.__VnbaTriggered);
    if (__VnbaExecute) {
        {
            // Inlined CFunc: _eval_body__nba
            if ((1ULL & vlSelfRef.__VnbaTriggered[0U])) {
                {
                    // Inlined CFunc: _nba_sequent__TOP__0
                    if (vlSelfRef.tb_modq_addsub_exh__DOT__rst_n) {
                        vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__sum_r 
                            = (0x00000fffU & ((0x00002000U 
                                               & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s) 
                                                  - (IData)(0x0d01U)))
                                               ? (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s)
                                               : ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s) 
                                                  - (IData)(0x0d01U))));
                        vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__diff_r 
                            = (0x00000fffU & ((0x00001000U 
                                               & (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))
                                               ? ((IData)(0x0d01U) 
                                                  + (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))
                                               : (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d)));
                    } else {
                        vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__sum_r = 0U;
                        vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__diff_r = 0U;
                    }
                }
            }
            if ((6ULL & vlSelfRef.__VnbaTriggered[0U])) {
                {
                    // Inlined CFunc: _act_comb__TOP__0
                    vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s 
                        = (0x00001fffU & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__y) 
                                          + (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__x)));
                    vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d 
                        = (0x00001fffU & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__x) 
                                          - (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__y)));
                }
            }
        }
        Vtb_modq_addsub_exh___024root___trigger_clear__act(vlSelfRef.__VnbaTriggered);
    }
    return (__VnbaExecute);
}

bool Vtb_modq_addsub_exh___024root___eval_obs(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_obs\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

bool Vtb_modq_addsub_exh___024root___eval_react(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_react\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    return (0U);
}

void Vtb_modq_addsub_exh___024root___eval_postponed(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_postponed\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

void Vtb_modq_addsub_exh___024root____VbeforeTrig_hb0d7f014__0(Vtb_modq_addsub_exh___024root* vlSelf, const char* __VeventDescription);

VlCoroutine Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__0(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__0\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ tb_modq_addsub_exh__DOT__i;
    tb_modq_addsub_exh__DOT__i = 0;
    // Body
    Vtb_modq_addsub_exh___024root____VbeforeTrig_hb0d7f014__0(vlSelf, 
                                                              "@(negedge tb_modq_addsub_exh.clk)");
    co_await vlSelfRef.__VtrigSched_hb0d7f014__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb_modq_addsub_exh.clk)", 
                                                         "tb_modq_addsub_exh.v", 
                                                         14);
    vlSelfRef.tb_modq_addsub_exh__DOT__rst_n = 1U;
    tb_modq_addsub_exh__DOT__i = 0U;
    while (VL_GTS_III(32, 0x00000d01U, tb_modq_addsub_exh__DOT__i)) {
        vlSelfRef.tb_modq_addsub_exh__DOT__j = 0U;
        while (VL_GTS_III(32, 0x00000d01U, vlSelfRef.tb_modq_addsub_exh__DOT__j)) {
            vlSelfRef.tb_modq_addsub_exh__DOT__x = 
                (0x00000fffU & tb_modq_addsub_exh__DOT__i);
            vlSelfRef.tb_modq_addsub_exh__DOT__y = 
                (0x00000fffU & vlSelfRef.tb_modq_addsub_exh__DOT__j);
            vlSelfRef.tb_modq_addsub_exh__DOT__es = 
                (0x00000fffU & VL_MODDIVS_III(32, (tb_modq_addsub_exh__DOT__i 
                                                   + vlSelfRef.tb_modq_addsub_exh__DOT__j), (IData)(0x00000d01U)));
            vlSelfRef.tb_modq_addsub_exh__DOT__ed = 
                (0x00000fffU & VL_MODDIVS_III(32, ((IData)(0x00000d01U) 
                                                   + 
                                                   (tb_modq_addsub_exh__DOT__i 
                                                    - vlSelfRef.tb_modq_addsub_exh__DOT__j)), (IData)(0x00000d01U)));
            co_await vlSelfRef.__VdlySched.delay(0x00000000000003e8ULL, 
                                                 nullptr, 
                                                 "tb_modq_addsub_exh.v", 
                                                 19);
            if ((((0x00000fffU & ((0x00002000U & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s) 
                                                  - (IData)(0x0d01U)))
                                   ? (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s)
                                   : ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s) 
                                      - (IData)(0x0d01U)))) 
                  != (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__es)) 
                 | ((0x00000fffU & ((0x00001000U & (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))
                                     ? ((IData)(0x0d01U) 
                                        + (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))
                                     : (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))) 
                    != (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__ed)))) {
                vlSelfRef.tb_modq_addsub_exh__DOT__errors 
                    = ((IData)(1U) + vlSelfRef.tb_modq_addsub_exh__DOT__errors);
                if (VL_UNLIKELY((VL_GTS_III(32, 0x0000000aU, vlSelfRef.tb_modq_addsub_exh__DOT__errors)))) {
                    VL_WRITEF_NX("comb %0d %0d -> %0d %0d\n",4
                                 , '~',32,tb_modq_addsub_exh__DOT__i
                                 , '~',32,vlSelfRef.tb_modq_addsub_exh__DOT__j
                                 , '#',12,(0x00000fffU 
                                           & ((0x00002000U 
                                               & ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s) 
                                                  - (IData)(0x0d01U)))
                                               ? (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s)
                                               : ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__s) 
                                                  - (IData)(0x0d01U))))
                                 , '#',12,(0x00000fffU 
                                           & ((0x00001000U 
                                               & (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))
                                               ? ((IData)(0x0d01U) 
                                                  + (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))
                                               : (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u0__DOT__d))));
                }
            }
            Vtb_modq_addsub_exh___024root____VbeforeTrig_hb0d7f014__0(vlSelf, 
                                                                      "@(negedge tb_modq_addsub_exh.clk)");
            co_await vlSelfRef.__VtrigSched_hb0d7f014__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(negedge tb_modq_addsub_exh.clk)", 
                                                                 "tb_modq_addsub_exh.v", 
                                                                 21);
            if ((((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__sum_r) 
                  != (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__es)) 
                 | ((IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__diff_r) 
                    != (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__ed)))) {
                vlSelfRef.tb_modq_addsub_exh__DOT__errors 
                    = ((IData)(1U) + vlSelfRef.tb_modq_addsub_exh__DOT__errors);
                if (VL_UNLIKELY((VL_GTS_III(32, 0x0000000aU, vlSelfRef.tb_modq_addsub_exh__DOT__errors)))) {
                    VL_WRITEF_NX("reg %0d %0d -> %0d %0d\n",4
                                 , '~',32,tb_modq_addsub_exh__DOT__i
                                 , '~',32,vlSelfRef.tb_modq_addsub_exh__DOT__j
                                 , '#',12,(IData)(vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__sum_r)
                                 , '#',12,vlSelfRef.tb_modq_addsub_exh__DOT__u1__DOT__g_reg__DOT__diff_r);
                }
            }
            vlSelfRef.tb_modq_addsub_exh__DOT__j = 
                ((IData)(1U) + vlSelfRef.tb_modq_addsub_exh__DOT__j);
        }
        tb_modq_addsub_exh__DOT__i = ((IData)(1U) + tb_modq_addsub_exh__DOT__i);
    }
    if ((0U == vlSelfRef.tb_modq_addsub_exh__DOT__errors)) {
        VL_WRITEF_NX("PASS: 11082241 pairs, REG_OUT 0 and 1\n",0);
    } else {
        VL_WRITEF_NX("FAIL: %0d errors\n",1, '~',32,vlSelfRef.tb_modq_addsub_exh__DOT__errors);
    }
    VL_FINISH_MT("tb_modq_addsub_exh.v", 26, "");
    co_return;
}

VlCoroutine Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__1(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_initial__TOP__Vtiming__1\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (VL_LIKELY(!vlSymsp->_vm_contextp__->gotFinish())) {
        co_await vlSelfRef.__VdlySched.delay(0x0000000000001388ULL, 
                                             nullptr, 
                                             "tb_modq_addsub_exh.v", 
                                             10);
        vlSelfRef.tb_modq_addsub_exh__DOT__clk = (1U 
                                                  & (~ (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__clk)));
    }
    co_return;
}

bool Vtb_modq_addsub_exh___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___trigger_anySet__ico\n"); );
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

bool Vtb_modq_addsub_exh___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___trigger_anySet__act\n"); );
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

void Vtb_modq_addsub_exh___024root___timing_ready(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___timing_ready\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((2ULL & vlSelfRef.__VactTriggered[0U])) {
        vlSelfRef.__VtrigSched_hb0d7f014__0.ready("@(negedge tb_modq_addsub_exh.clk)");
    }
}

void Vtb_modq_addsub_exh___024root___timing_resume(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___timing_resume\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VtrigSched_hb0d7f014__0.moveToResumeQueue(
                                                          "@(negedge tb_modq_addsub_exh.clk)");
    vlSelfRef.__VtrigSched_hb0d7f014__0.resume("@(negedge tb_modq_addsub_exh.clk)");
    if ((4ULL & vlSelfRef.__VactTriggered[0U])) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb_modq_addsub_exh___024root___trigger_orInto__act_vec_vec(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___trigger_orInto__act_vec_vec\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = (out[n] | in[n]);
        n = ((IData)(1U) + n);
    } while ((0U >= n));
}

void Vtb_modq_addsub_exh___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___trigger_clear__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = 0ULL;
        n = ((IData)(1U) + n);
    } while ((1U > n));
}

void Vtb_modq_addsub_exh___024root____VbeforeTrig_hb0d7f014__0(Vtb_modq_addsub_exh___024root* vlSelf, const char* __VeventDescription) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root____VbeforeTrig_hb0d7f014__0\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    VlUnpacked<QData/*63:0*/, 1> __VTmp;
    // Body
    __VTmp[0U] = (QData)((IData)((((~ (IData)(vlSelfRef.tb_modq_addsub_exh__DOT__clk)) 
                                   & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_addsub_exh__DOT__clk__0)) 
                                  << 1U)));
    vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_addsub_exh__DOT__clk__0 
        = vlSelfRef.tb_modq_addsub_exh__DOT__clk;
    if ((2ULL & __VTmp[0U])) {
        vlSelfRef.__VtrigSched_hb0d7f014__0.ready(__VeventDescription);
        vlSelfRef.__VtrigSched_hb0d7f014__0.ready(__VeventDescription);
    }
    vlSelfRef.__VactTriggeredAcc[0U] = (vlSelfRef.__VactTriggeredAcc[0U] 
                                        | __VTmp[0U]);
}

#ifdef VL_DEBUG
void Vtb_modq_addsub_exh___024root___eval_debug_assertions(Vtb_modq_addsub_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_addsub_exh___024root___eval_debug_assertions\n"); );
    Vtb_modq_addsub_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
