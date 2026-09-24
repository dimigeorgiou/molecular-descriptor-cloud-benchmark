#!/usr/bin/env python3
"""CLI entry point for the paper companion package."""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from descriptor_cloud_benchmark.pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
