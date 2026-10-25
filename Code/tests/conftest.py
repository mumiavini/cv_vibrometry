import sys
from pathlib import Path

# make ``vibrometry`` importable when running ``pytest`` from Code/ or the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
