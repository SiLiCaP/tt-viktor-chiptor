# Area model (UNVERIFIED)

Verilog written only to estimate sky130 cell area for designs A and B. It has never been simulated.
Known simplifications: the processing element is not pipelined (A's 3 clocks/butterfly needs a
pipeline), block-mode unload pacing is crude, latencies are not the protocol's. Use for structure
ideas and area tracking only. Do not copy into src/ without tests against model/mlkem_ntt_model.py.

Reproduce the numbers (needs the sky130 liberty file as hd_tt.lib in this folder):
  ./run.sh ntt_a.v tt_um_ntt_a 1   # A, serial multiplier   -> ~24,617 um^2
  ./run.sh ntt_b.v tt_um_ntt_b 1   # B1                     -> ~40,988 um^2
  ./run.sh ntt_b.v tt_um_ntt_b 0   # B2 (parallel)          -> ~42,680 um^2
  ./hier.sh <file> <top> <SERIAL>  # per-block breakdown
