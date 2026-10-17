// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb_modq_mul_exh.h for the primary calling header

#include "Vtb_modq_mul_exh__pch.h"

void Vtb_modq_mul_exh___024root___ctor_var_reset(Vtb_modq_mul_exh___024root* vlSelf);

Vtb_modq_mul_exh___024root::Vtb_modq_mul_exh___024root(Vtb_modq_mul_exh__Syms* symsp, const char* namep)
    : __VdlySched{*symsp->_vm_contextp__}
 {
    vlSymsp = symsp;
    vlNamep = strdup(namep);
    // Reset structure values
    Vtb_modq_mul_exh___024root___ctor_var_reset(this);
}

Vtb_modq_mul_exh___024root::~Vtb_modq_mul_exh___024root() {
    VL_DO_DANGLING(std::free(const_cast<char*>(vlNamep)), vlNamep);
}
