# Tang Nano 20K emulator build (open-source flow: OSS CAD Suite).
#   make -C fpga          build build/top.fs
#   make -C fpga prog     load into SRAM (lost on power cycle)
#   make -C fpga flash    write to the onboard flash (persists)
#   make -C fpga sim      cocotb simulation of the wrapper + UART protocol
# Override the DUT:  make -C fpga TT_TOP=tt_um_other [EXTRA_SRCS=path/to/extra.v]
# Self-test DUT:     make -C fpga prog TT_TOP=tt_um_emu_selftest EXTRA_SRCS=$(pwd)/fpga/sim/tt_um_emu_selftest.v

FPGA_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT     := $(abspath $(FPGA_DIR)/..)
BUILD    := $(FPGA_DIR)build

# DUT sources and top come from info.yaml, so the FPGA build follows the ASIC build.
SRC_FILES := $(shell awk '/^ *source_files:/{f=1;next} f&&/^ *- /{sub(/^ *- */,"");sub(/ *#.*/,"");gsub(/"/,"");print;next} f&&!/^ *#/{f=0}' $(ROOT)/info.yaml)
TT_TOP    ?= $(shell awk -F'"' '/^ *top_module:/{print $$2}' $(ROOT)/info.yaml)
DUT_SRCS  := $(addprefix $(ROOT)/src/,$(SRC_FILES)) $(EXTRA_SRCS)
WRAP_SRCS := $(FPGA_DIR)uart.v $(FPGA_DIR)tangnano20k_top.v

BAUD   ?= 115200
DEVICE := GW2AR-LV18QN88C8/I7
FAMILY := GW2A-18C
CST    := $(FPGA_DIR)tangnano20k.cst

.PHONY: all prog flash sim clean info

all: $(BUILD)/top.fs

info:
	@echo "TT_TOP   = $(TT_TOP)"
	@echo "DUT_SRCS = $(DUT_SRCS)"

$(BUILD)/top.json: $(DUT_SRCS) $(WRAP_SRCS) $(ROOT)/info.yaml | $(BUILD)
	yosys -q -l $(BUILD)/yosys.log -D TT_TOP=$(TT_TOP) \
	  -p "read_verilog $(DUT_SRCS) $(WRAP_SRCS); chparam -set BAUD $(BAUD) tangnano20k_top; synth_gowin -top tangnano20k_top -json $@"

$(BUILD)/pnr.json: $(BUILD)/top.json $(CST)
	nextpnr-himbaechel -q -l $(BUILD)/nextpnr.log --json $< --write $@ \
	  --device $(DEVICE) --vopt family=$(FAMILY) --vopt cst=$(CST) --freq 27

$(BUILD)/top.fs: $(BUILD)/pnr.json
	gowin_pack -d $(FAMILY) -o $@ $<

prog: $(BUILD)/top.fs
	openFPGALoader -b tangnano20k $<

flash: $(BUILD)/top.fs
	openFPGALoader -b tangnano20k -f $<

sim:   # the wrapper is checked with the sequential self-test DUT (random pin words, cycle accuracy)
	$(MAKE) -C $(FPGA_DIR)sim TT_TOP=tt_um_emu_selftest

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD)
	$(MAKE) -C $(FPGA_DIR)sim clean
