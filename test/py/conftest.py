import os
import sys

# These tests check this repo's exploration chip (2 K-RED rounds); test_team_model.py covers the team chip.
os.environ.setdefault("NTT_CHIP", "own")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for sub in ("model", "sim", "host"):
    sys.path.insert(0, os.path.join(ROOT, sub))
VECTORS = os.path.join(ROOT, "test", "vectors")
