// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb_modq_addsub_exh__pch.h"

//============================================================
// Constructors

Vtb_modq_addsub_exh::Vtb_modq_addsub_exh(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb_modq_addsub_exh__Syms(contextp(), _vcname__, this)}
    , m_evalLoop{*this, /*convergeLimit:*/ 10000}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vtb_modq_addsub_exh::Vtb_modq_addsub_exh(const char* _vcname__)
    : Vtb_modq_addsub_exh(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb_modq_addsub_exh::~Vtb_modq_addsub_exh() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb_modq_addsub_exh___024root___eval_debug_assertions(Vtb_modq_addsub_exh___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_static(Vtb_modq_addsub_exh___024root* vlSelf);
void Vtb_modq_addsub_exh___024root___eval_initial(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD bool Vtb_modq_addsub_exh___024root___eval_stl(Vtb_modq_addsub_exh___024root* vlSelf, CData/*0:0*/ firstIteration);
void Vtb_modq_addsub_exh___024root___eval_sample(Vtb_modq_addsub_exh___024root* vlSelf);
bool Vtb_modq_addsub_exh___024root___eval_ico(Vtb_modq_addsub_exh___024root* vlSelf, CData/*0:0*/ firstIteration);
bool Vtb_modq_addsub_exh___024root___eval_act(Vtb_modq_addsub_exh___024root* vlSelf);
bool Vtb_modq_addsub_exh___024root___eval_inact(Vtb_modq_addsub_exh___024root* vlSelf);
bool Vtb_modq_addsub_exh___024root___eval_nba(Vtb_modq_addsub_exh___024root* vlSelf);
bool Vtb_modq_addsub_exh___024root___eval_obs(Vtb_modq_addsub_exh___024root* vlSelf);
bool Vtb_modq_addsub_exh___024root___eval_react(Vtb_modq_addsub_exh___024root* vlSelf);
void Vtb_modq_addsub_exh___024root___eval_postponed(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_final(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_dump_triggers__stl(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_dump_triggers__ico(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_dump_triggers__act(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_dump_triggers__nba(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_dump_triggers__obs(Vtb_modq_addsub_exh___024root* vlSelf);
VL_ATTR_COLD void Vtb_modq_addsub_exh___024root___eval_dump_triggers__react(Vtb_modq_addsub_exh___024root* vlSelf);

void Vtb_modq_addsub_exh::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb_modq_addsub_exh::eval_step\n"); );
    m_evalLoop.eval();
}

void Vtb_modq_addsub_exh::evalBegin() {
#ifdef VL_DEBUG
    // Debug assertions
    Vtb_modq_addsub_exh___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
}

void Vtb_modq_addsub_exh::evalEnd() {
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
    vlSymsp->TOP.__VdlySched.cleanupForevered();
}

void Vtb_modq_addsub_exh::evalStatic() {
    Vtb_modq_addsub_exh___024root___eval_static(&(vlSymsp->TOP));
}

void Vtb_modq_addsub_exh::evalInitial() {
    Vtb_modq_addsub_exh___024root___eval_initial(&(vlSymsp->TOP));
}

bool Vtb_modq_addsub_exh::evalStl(bool firstIteration) {
    return Vtb_modq_addsub_exh___024root___eval_stl(&(vlSymsp->TOP), firstIteration);
}

void Vtb_modq_addsub_exh::evalSample() {
    Vtb_modq_addsub_exh___024root___eval_sample(&(vlSymsp->TOP));
}

bool Vtb_modq_addsub_exh::evalIco(bool firstIteration) {
    return Vtb_modq_addsub_exh___024root___eval_ico(&(vlSymsp->TOP), firstIteration);
}

bool Vtb_modq_addsub_exh::evalAct() {
    return Vtb_modq_addsub_exh___024root___eval_act(&(vlSymsp->TOP));
}

bool Vtb_modq_addsub_exh::evalInact() {
    return Vtb_modq_addsub_exh___024root___eval_inact(&(vlSymsp->TOP));
}

bool Vtb_modq_addsub_exh::evalNba() {
    return Vtb_modq_addsub_exh___024root___eval_nba(&(vlSymsp->TOP));
}

bool Vtb_modq_addsub_exh::evalObs() {
    return Vtb_modq_addsub_exh___024root___eval_obs(&(vlSymsp->TOP));
}

bool Vtb_modq_addsub_exh::evalReact() {
    return Vtb_modq_addsub_exh___024root___eval_react(&(vlSymsp->TOP));
}

void Vtb_modq_addsub_exh::evalPostponed() {
    Vtb_modq_addsub_exh___024root___eval_postponed(&(vlSymsp->TOP));
}

void Vtb_modq_addsub_exh::evalFinal() {
    Vtb_modq_addsub_exh___024root___eval_final(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vtb_modq_addsub_exh::dumpTriggersStl() {
    Vtb_modq_addsub_exh___024root___eval_dump_triggers__stl(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vtb_modq_addsub_exh::dumpTriggersIco() {
    Vtb_modq_addsub_exh___024root___eval_dump_triggers__ico(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vtb_modq_addsub_exh::dumpTriggersAct() {
    Vtb_modq_addsub_exh___024root___eval_dump_triggers__act(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vtb_modq_addsub_exh::dumpTriggersNba() {
    Vtb_modq_addsub_exh___024root___eval_dump_triggers__nba(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vtb_modq_addsub_exh::dumpTriggersObs() {
    Vtb_modq_addsub_exh___024root___eval_dump_triggers__obs(&(vlSymsp->TOP));
}

VL_ATTR_COLD void Vtb_modq_addsub_exh::dumpTriggersReact() {
    Vtb_modq_addsub_exh___024root___eval_dump_triggers__react(&(vlSymsp->TOP));
}

//============================================================
// Events and timing
bool Vtb_modq_addsub_exh::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty() && !contextp()->gotFinish(); }

uint64_t Vtb_modq_addsub_exh::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb_modq_addsub_exh::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

VL_ATTR_COLD void Vtb_modq_addsub_exh::final() {
    contextp()->executingFinal(true);
    evalFinal();
    contextp()->executingFinal(false);
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb_modq_addsub_exh::hierName() const { return vlSymsp->name(); }
const char* Vtb_modq_addsub_exh::modelName() const { return "Vtb_modq_addsub_exh"; }
unsigned Vtb_modq_addsub_exh::threads() const { return 1; }
void Vtb_modq_addsub_exh::prepareClone() const { contextp()->prepareClone(); }
void Vtb_modq_addsub_exh::atClone() const {
    contextp()->threadPoolpOnClone();
}
