#!/usr/bin/env python
"""
Permanent launcher for Autonomous Trailer Director.
Sets up paths correctly and runs CLI.
Usage: python run.py [cli args...]
       python run.py --config ./config/default_config.yaml --mock run --package <episode_package> --output ./out/
"""
import sys
import os
from pathlib import Path

# ─── PERMANENT PATH FIX ───
ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))          # Make 'src' importable
os.chdir(ROOT)                         # Ensure correct working directory
# ────────────────────────────

if __name__ == "__main__":
    from src.cli import cli
    cli()