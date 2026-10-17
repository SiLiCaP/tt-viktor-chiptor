#!/bin/bash
# usage: run.sh <file> <top> <SERIAL>
f=$1; top=$2; ser=$3
yowasp-yosys -q -l log_${top}_${ser}.txt -p "
read_verilog -sv pe.v $f
chparam -set SERIAL $ser $top
synth -flatten -top $top
dfflibmap -liberty hd_tt.lib
abc -liberty hd_tt.lib
opt_clean -purge
tee -o stat_${top}_${ser}.txt stat -liberty hd_tt.lib
" >/dev/null 2>&1
grep -E "Chip area|Number of cells" stat_${top}_${ser}.txt | tail -2
