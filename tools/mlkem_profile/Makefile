# ML-KEM-512 (PQClean clean) for the Cortex-M33, profiled per function under emulation (profile.py).
#   make -C tools/mlkem_profile run     (needs ~/tools/arm-gnu-toolchain, ~/tools/ref/PQClean, ~/tools/emu-venv)
PQ   ?= $(HOME)/tools/ref/PQClean
CC   := $(HOME)/tools/arm-gnu-toolchain/bin/arm-none-eabi-gcc
KEM  := $(PQ)/crypto_kem/ml-kem-512/clean
SRCS := main.c $(wildcard $(KEM)/*.c) $(PQ)/common/fips202.c
CFLAGS := -mcpu=cortex-m33 -mthumb -O2 -fno-inline -ffunction-sections -I$(KEM) -I$(PQ)/common -Wall
mlkem.elf: $(SRCS) link.ld
	$(CC) $(CFLAGS) -nostartfiles -T link.ld --specs=nano.specs --specs=nosys.specs -o $@ $(SRCS)
run: mlkem.elf
	$(HOME)/tools/emu-venv/bin/python profile.py mlkem.elf
.PHONY: run
