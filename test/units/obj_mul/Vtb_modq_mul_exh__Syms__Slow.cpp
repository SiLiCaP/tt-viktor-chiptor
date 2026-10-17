// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb_modq_mul_exh__pch.h"

Vtb_modq_mul_exh__Syms::Vtb_modq_mul_exh__Syms(VerilatedContext* contextp, const char* namep, Vtb_modq_mul_exh* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    , __Vm_didInit{modelp->m_didInit}
    // Setup top module instance
    , TOP{this, namep}
{
    // Check resources
    Verilated::stackCheck(22);
    // Setup sub module instances
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
}

Vtb_modq_mul_exh__Syms::~Vtb_modq_mul_exh__Syms() {
    // Tear down scopes
    // Tear down sub module instances
}
