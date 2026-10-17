#!/bin/bash
f=$1; top=$2; ser=$3
yowasp-yosys -q -p "
read_verilog -sv pe.v $f
chparam -set SERIAL $ser $top
hierarchy -top $top
synth -top $top
dfflibmap -liberty hd_tt.lib
abc -liberty hd_tt.lib
opt_clean -purge
tee -o hstat_${top}_${ser}.txt stat -liberty hd_tt.lib
" >/dev/null 2>&1
grep -E "^=== |Chip area" hstat_${top}_${ser}.txt
