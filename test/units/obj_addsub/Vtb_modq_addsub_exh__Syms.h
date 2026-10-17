// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB_MODQ_ADDSUB_EXH__SYMS_H_
#define VERILATED_VTB_MODQ_ADDSUB_EXH__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vtb_modq_addsub_exh.h"

// INCLUDE MODULE CLASSES
#include "Vtb_modq_addsub_exh___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES) Vtb_modq_addsub_exh__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb_modq_addsub_exh* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool& __Vm_didInit;

    // MODULE INSTANCE STATE
    Vtb_modq_addsub_exh___024root  TOP;

    // CONSTRUCTORS
    Vtb_modq_addsub_exh__Syms(VerilatedContext* contextp, const char* namep, Vtb_modq_addsub_exh* modelp);
    ~Vtb_modq_addsub_exh__Syms();

    // METHODS
    const char* name() const { return TOP.vlNamep; }
};

#endif  // guard
