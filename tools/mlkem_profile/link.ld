ENTRY(run)
MEMORY { FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 1M  RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 512K }
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > FLASH
  .data : { *(.data*) } > RAM AT > FLASH
  .bss : { *(.bss*) *(COMMON) } > RAM
  end = .;
  _estack = ORIGIN(RAM) + LENGTH(RAM);
}
