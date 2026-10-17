# cocotb test of the exploration Keccak core:  make -C sim/arch_explore_rtl
SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(CURDIR)/keccak_lane.v
TOPLEVEL = keccak_lane
COCOTB_TEST_MODULES = test_keccak_lane
include $(shell cocotb-config --makefiles)/Makefile.sim
