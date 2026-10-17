import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for sub in ("model", "sim", "host"):
    sys.path.insert(0, os.path.join(ROOT, sub))
VECTORS = os.path.join(ROOT, "test", "vectors")
