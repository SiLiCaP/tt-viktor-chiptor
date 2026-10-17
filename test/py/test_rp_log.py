"""tools/rp_log.py: a log made from known firmware costs must fit back to exactly those costs."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rp_log  # noqa: E402

TRUE = {"fw_prep_cyc_input": 22.0, "fw_prep_cyc_word": 1.25, "fw_post_cyc_pair": 45.0, "fw_gather_cyc_unit": 18.0,
        "fw_batch_cyc": 480.0, "fw_call_cyc": 400.0}
CPU, CHIP = 150_000_000, 10_000_000
# (op, batches, units per batch, words per batch) as the firmware runs the team chip
OPS = [("forward", 7, 128, 393), ("inverse", 7, 128, 395), ("basemul", 1, 128, 655), ("scale", 1, 128, 394)]


def synthetic_log():
    recs = []
    for _ in range(3):
        for op, nb, units, words in OPS:
            spent = 0
            for b in range(nb):
                prep = TRUE["fw_prep_cyc_input"] * units * rp_log.N_IN[op] + TRUE["fw_prep_cyc_word"] * words
                conv = 3 * words                                     # the rig's word spreading
                run = words * CPU // CHIP + conv + TRUE["fw_batch_cyc"]
                post = TRUE["fw_post_cyc_pair"] * units
                recs.append({"kind": "batch", "op": op, "batch": b, "units": units, "words": words,
                             "prep_cyc": round(prep), "run_cyc": round(run), "conv_cyc": conv,
                             "post_cyc": round(post), "total_cyc": 0, "chip_hz": CHIP, "cpu_hz": CPU, "skew": 0})
                spent += round(prep) + round(run) + round(post)
            other = TRUE["fw_call_cyc"] + (TRUE["fw_gather_cyc_unit"] * 896 if nb == 7 else 0)
            recs.append({"kind": "call", "op": op, "batch": 0, "units": 0, "words": nb * words, "prep_cyc": 0,
                         "run_cyc": 0, "conv_cyc": 0, "post_cyc": 0, "total_cyc": spent + round(other),
                         "chip_hz": CHIP, "cpu_hz": CPU, "skew": 0})
    return recs


def test_fit_recovers_the_costs():
    coeffs, info = rp_log.fit(synthetic_log())
    for k, v in TRUE.items():
        assert abs(coeffs[k] - v) < 0.05 * max(1.0, v), (k, coeffs[k], v)
    assert info["rig_conv_cyc_per_word"] == 3.0
