# Tang Nano 20K emulator build (open-source flow: OSS CAD Suite).
#   make -C fpga          build build/top.fs
#   make -C fpga prog     load into SRAM (lost on power cycle)
#   make -C fpga flash    write to the onboard flash (persists)
#   make -C fpga sim      cocotb simulation of the wrapper + UART protocol
# Which chip:        make -C fpga prog                 the team's tapeout chip (../chipathon-2026, tt_um_NTT_Core)
#                    make -C fpga prog DESIGN=own      this repo's exploration RTL (tt_um_ntt_engine)
# Gate level:        make -C fpga netlist              harden the design with the TT flow (once per design change)
#                    make -C fpga prog GL=1            the hardened sky130 gate netlist instead of the RTL: every
#                    standard cell is rebuilt from its logic function in the sky130 liberty file, so the FPGA
#                    runs the exact gates that go on the chip. Default for the team chip; GL=0 for its RTL.
#                    GL_NETLIST=path overrides the netlist (e.g. the gate-level netlist from the GDS action).
# Override the DUT:  make -C fpga TT_TOP=tt_um_other [EXTRA_SRCS=path/to/extra.v]
# Self-test DUT:     make -C fpga prog TT_TOP=tt_um_emu_selftest EXTRA_SRCS=$(pwd)/fpga/sim/tt_um_emu_selftest.v

FPGA_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT     := $(abspath $(FPGA_DIR)/..)
TEAM     := $(abspath $(ROOT)/../chipathon-2026)
DESIGN   ?= team
DESIGN_ROOT := $(if $(filter team,$(DESIGN)),$(TEAM),$(ROOT))

# DUT sources and top come from the design's info.yaml, so the FPGA build follows the ASIC build.
SRC_FILES := $(shell awk '/^ *source_files:/{f=1;next} f&&/^ *- /{sub(/^ *- */,"");sub(/ *#.*/,"");gsub(/"/,"");print;next} f&&!/^ *#/{f=0}' $(DESIGN_ROOT)/info.yaml)
TT_TOP    ?= $(shell awk -F'"' '/^ *top_module:/{print $$2}' $(DESIGN_ROOT)/info.yaml)
GL        ?= $(if $(filter team,$(DESIGN)),1,0)
HARDEN_DIR := $(FPGA_DIR)build/harden/$(TT_TOP)
GL_NETLIST ?= $(firstword $(wildcard $(DESIGN_ROOT)/runs/wokwi/final/nl/$(TT_TOP).nl.v $(HARDEN_DIR)/runs/wokwi/final/nl/$(TT_TOP).nl.v))
SKY130_LIB ?= $(firstword $(wildcard $(HOME)/.ciel/ciel/sky130/versions/*/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib))
ifeq ($(GL),1)
DUT_SRCS  := $(GL_NETLIST) $(FPGA_DIR)sky130_phys_cells.v $(EXTRA_SRCS)
READ_CELLS := read_liberty -ignore_miss_func $(SKY130_LIB);
BUILD     := $(FPGA_DIR)build/$(TT_TOP)_gl
else
DUT_SRCS  := $(addprefix $(DESIGN_ROOT)/src/,$(SRC_FILES)) $(EXTRA_SRCS)
READ_CELLS :=
BUILD     := $(FPGA_DIR)build/$(TT_TOP)
endif
WRAP_SRCS := $(FPGA_DIR)uart.v $(FPGA_DIR)tangnano20k_top.v

BAUD   ?= 1000000    # measured: 1 Mbaud stable; 1.5 and 3 Mbaud lose bytes in long readbacks (BL616)
DEVICE := GW2AR-LV18QN88C8/I7
FAMILY := GW2A-18C
CST    := $(FPGA_DIR)tangnano20k.cst

.PHONY: all prog flash sim clean info netlist check_netlist

all: $(BUILD)/top.fs

info:
	@echo "DESIGN   = $(DESIGN) ($(DESIGN_ROOT))"
	@echo "TT_TOP   = $(TT_TOP)"
	@echo "GL       = $(GL)"
	@echo "DUT_SRCS = $(DUT_SRCS)"

$(BUILD)/top.json: $(DUT_SRCS) $(WRAP_SRCS) $(DESIGN_ROOT)/info.yaml | check_netlist $(BUILD)
	yosys -q -l $(BUILD)/yosys.log -D TT_TOP=$(TT_TOP) \
	  -p "$(READ_CELLS) read_verilog $(DUT_SRCS) $(WRAP_SRCS); chparam -set BAUD $(BAUD) tangnano20k_top; synth_gowin -top tangnano20k_top -json $@"

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

netlist:
	PATH=$(HOME)/tools/bin:$(HOME)/tools/tt-venv/bin:$$PATH sh $(FPGA_DIR)harden.sh $(DESIGN_ROOT) $(HARDEN_DIR)

check_netlist:
ifeq ($(GL),1)
	@test -n "$(GL_NETLIST)" || { echo "no gate netlist for $(TT_TOP): run 'make -C fpga netlist' (or GL=0 for the RTL)"; exit 1; }
endif

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(filter-out $(FPGA_DIR)build/harden,$(wildcard $(FPGA_DIR)build/*))
	$(MAKE) -C $(FPGA_DIR)sim clean
