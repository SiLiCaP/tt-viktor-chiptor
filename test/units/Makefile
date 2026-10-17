# Exhaustive block tests (team Specs 2 and 4), Icarus, split over all cores by first operand.
#   make -C test/units mul_exh       all 3329^2 multiplier pairs, back to back, latency checked
#   make -C test/units addsub_exh    all 3329^2 add/sub pairs, REG_OUT 0 and 1
SRC  := ../../src
JOBS ?= $(shell nproc)
CHUNKS := $(shell python3 -c "n=$(JOBS); s=-(-3329//n); print(' '.join(f'{i}:{min(i+s,3329)}' for i in range(0,3329,s)))")

define run_split
	iverilog -g2012 -o $(1).vvp $(2)
	printf '%s\n' $(CHUNKS) | xargs -P $(JOBS) -I{} sh -c 'r={}; vvp -n $(1).vvp +LO=$${r%%:*} +HI=$${r##*:} > $(1)_$${r%%:*}.log'
	cat $(1)_*.log | grep -E "^(PASS|FAIL|MISMATCH)" | sort | uniq -c | sed 's/\[[0-9,]*)//' | sort | uniq -c | head
	! grep -L "^PASS" $(1)_*.log | grep -q .
endef

mul_exh:
	$(call run_split,mul,tb_modq_mul_exh.v $(SRC)/modq_mul.v)

addsub_exh:
	$(call run_split,addsub,tb_modq_addsub_exh.v $(SRC)/modq_addsub.v)

clean:
	rm -f *.vvp *.log
