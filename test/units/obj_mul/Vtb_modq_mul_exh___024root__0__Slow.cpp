// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_modq_mul_exh.h for the primary calling header

#include "Vtb_modq_mul_exh__pch.h"

void Vtb_modq_mul_exh___024root___timing_ready(Vtb_modq_mul_exh___024root* vlSelf);

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_static(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_static\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    {
        // Inlined CFunc: _eval_static__TOP
        vlSelfRef.tb_modq_mul_exh__DOT__clk = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__rst_n = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__start = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__a_in = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__b_in = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__errors = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__cyc = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__head = 0U;
        vlSelfRef.tb_modq_mul_exh__DOT__tail = 0U;
    }
    vlSelfRef.__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0 = 0U;
    Vtb_modq_mul_exh___024root___timing_ready(vlSelf);
    do {
        vlSelfRef.__VactTriggeredAcc[vlSelfRef.__Vi] 
            = vlSelfRef.__VactTriggered[vlSelfRef.__Vi];
        vlSelfRef.__Vi = ((IData)(1U) + vlSelfRef.__Vi);
    } while ((0U >= vlSelfRef.__Vi));
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__stl(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vtb_modq_mul_exh___024root___trigger_anySet__stl(const VlUnpacked<QData/*63:0*/, 1> &in);

VL_ATTR_COLD bool Vtb_modq_mul_exh___024root___eval_stl(Vtb_modq_mul_exh___024root* vlSelf, CData/*0:0*/ firstIteration) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_stl\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VstlExecute;
    // Body
    vlSelfRef.__VstlTriggered[0U] = ((0xfffffffffffffffeULL 
                                      & vlSelfRef.__VstlTriggered[0U]) 
                                     | (IData)((IData)(firstIteration)));
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb_modq_mul_exh___024root___dump_triggers__stl(vlSelfRef.__VstlTriggered, "stl"s);
    }
#endif
    __VstlExecute = Vtb_modq_mul_exh___024root___trigger_anySet__stl(vlSelfRef.__VstlTriggered);
    if (__VstlExecute) {
        {
            // Inlined CFunc: _eval_body__stl
            if ((1ULL & vlSelfRef.__VstlTriggered[0U])) {
                {
                    // Inlined CFunc: _stl_sequent__TOP__0
                    IData/*17:0*/ __Vinline_0__eval_body__stl___Vinline_0__stl_sequent__TOP__0_tb_modq_mul_exh__DOT__dut__DOT__r1;
                    __Vinline_0__eval_body__stl___Vinline_0__stl_sequent__TOP__0_tb_modq_mul_exh__DOT__dut__DOT__r1 = 0;
                    vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__pp 
                        = (0x0000ffffU & ((0x0000000fU 
                                           & ((1U == (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__phase))
                                               ? (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__rb_hi)
                                               : ((IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__rb_hi) 
                                                  >> 4U))) 
                                          * (IData)(vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__ra)));
                    __Vinline_0__eval_body__stl___Vinline_0__stl_sequent__TOP__0_tb_modq_mul_exh__DOT__dut__DOT__r1 
                        = (0x0003ffffU & ((0x00000fffU 
                                           & ((IData)(0x000dU) 
                                              * (0x000000ffU 
                                                 & vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc))) 
                                          - (0x0000ffffU 
                                             & (vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__acc 
                                                >> 8U))));
                    vlSelfRef.tb_modq_mul_exh__DOT__dut__DOT__r2 
                        = (0x00007fffU & ((0x00000fffU 
                                           & ((IData)(0x000dU) 
                                              * (0x000000ffU 
                                                 & __Vinline_0__eval_body__stl___Vinline_0__stl_sequent__TOP__0_tb_modq_mul_exh__DOT__dut__DOT__r1))) 
                                          - ((0x00007c00U 
                                              & ((- (IData)(
                                                            (1U 
                                                             & (__Vinline_0__eval_body__stl___Vinline_0__stl_sequent__TOP__0_tb_modq_mul_exh__DOT__dut__DOT__r1 
                                                                >> 0x00000011U)))) 
                                                 << 0x0000000aU)) 
                                             | (0x000003ffU 
                                                & (__Vinline_0__eval_body__stl___Vinline_0__stl_sequent__TOP__0_tb_modq_mul_exh__DOT__dut__DOT__r1 
                                                   >> 8U)))));
                }
            }
        }
    }
    return (__VstlExecute);
}

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_dump_triggers__stl(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_dump_triggers__stl\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vtb_modq_mul_exh___024root___dump_triggers__stl(vlSelfRef.__VstlTriggered, "stl"s);
#endif
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_dump_triggers__ico(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_dump_triggers__ico\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vtb_modq_mul_exh___024root___dump_triggers__ico(vlSelfRef.__VicoTriggered, "ico"s);
#endif
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_dump_triggers__act(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_dump_triggers__act\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vtb_modq_mul_exh___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
#endif
}

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_dump_triggers__nba(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_dump_triggers__nba\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
#ifdef VL_DEBUG
    Vtb_modq_mul_exh___024root___dump_triggers__act(vlSelfRef.__VnbaTriggered, "nba"s);
#endif
}

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_dump_triggers__obs(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_dump_triggers__obs\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_dump_triggers__react(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_dump_triggers__react\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___eval_final(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___eval_final\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__stl(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___dump_triggers__stl\n"); );
    // Body
    if ((1U & (~ (IData)(Vtb_modq_mul_exh___024root___trigger_anySet__stl(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD bool Vtb_modq_mul_exh___024root___trigger_anySet__stl(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___trigger_anySet__stl\n"); );
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

bool Vtb_modq_mul_exh___024root___trigger_anySet__ico(const VlUnpacked<QData/*63:0*/, 1> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__ico(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___dump_triggers__ico\n"); );
    // Body
    if ((1U & (~ (IData)(Vtb_modq_mul_exh___024root___trigger_anySet__ico(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: Internal 'ico' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

bool Vtb_modq_mul_exh___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in);

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb_modq_mul_exh___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___dump_triggers__act\n"); );
    // Body
    if ((1U & (~ (IData)(Vtb_modq_mul_exh___024root___trigger_anySet__act(triggers))))) {
        VL_DBG_MSGS("         No '" + tag + "' region triggers active\n");
    }
    if ((1U & (IData)(triggers[0U]))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 0 is active: @(posedge tb_modq_mul_exh.clk)\n");
    }
    if ((1U & (IData)((triggers[0U] >> 1U)))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 1 is active: @(negedge tb_modq_mul_exh.clk)\n");
    }
    if ((1U & (IData)((triggers[0U] >> 2U)))) {
        VL_DBG_MSGS("         '" + tag + "' region trigger index 2 is active: @([true] __VdlySched.awaitingCurrentTime())\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vtb_modq_mul_exh___024root___ctor_var_reset(Vtb_modq_mul_exh___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb_modq_mul_exh___024root___ctor_var_reset\n"); );
    Vtb_modq_mul_exh__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->tb_modq_mul_exh__DOT__p_out = 0;
    vlSelf->tb_modq_mul_exh__DOT__p_valid = 0;
    vlSelf->tb_modq_mul_exh__DOT__b = 0;
    for (int __Vi0 = 0; __Vi0 < 8; ++__Vi0) {
        vlSelf->tb_modq_mul_exh__DOT__exp_q[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 8; ++__Vi0) {
        vlSelf->tb_modq_mul_exh__DOT__start_cyc[__Vi0] = 0;
    }
    vlSelf->tb_modq_mul_exh__DOT__dut__DOT__ra = 0;
    vlSelf->tb_modq_mul_exh__DOT__dut__DOT__rb_hi = 0;
    vlSelf->tb_modq_mul_exh__DOT__dut__DOT__acc = 0;
    vlSelf->tb_modq_mul_exh__DOT__dut__DOT__phase = 0;
    vlSelf->tb_modq_mul_exh__DOT__dut__DOT__pp = 0;
    vlSelf->tb_modq_mul_exh__DOT__dut__DOT__r2 = 0;
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VstlTriggered[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VicoTriggered[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VactTriggered[__Vi0] = 0;
    }
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VactTriggeredAcc[__Vi0] = 0;
    }
    vlSelf->__Vtrigprevexpr___TOP__tb_modq_mul_exh__DOT__clk__0 = 0;
    for (int __Vi0 = 0; __Vi0 < 1; ++__Vi0) {
        vlSelf->__VnbaTriggered[__Vi0] = 0;
    }
    vlSelf->__Vi = 0;
}
