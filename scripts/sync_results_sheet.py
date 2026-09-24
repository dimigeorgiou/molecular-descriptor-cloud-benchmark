#!/usr/bin/env python3
"""Backfill Results metrics, dedupe paper rows in place, refresh Complexity A1 pivots."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Sync Google Sheets Results + Complexity tabs.")
    parser.add_argument("--sheet-id", default=os.getenv("GOOGLE_SHEETS_ID"))
    parser.add_argument(
        "--metric",
        default=os.getenv("SHEETS_COMPLEXITY_METRIC", "wall_clock"),
        choices=["wall_clock", "total_pipeline", "computation"],
    )
    parser.add_argument(
        "--experiment-id",
        default=os.getenv("SHEETS_EXPERIMENT_FILTER", ""),
    )
    args = parser.parse_args()

    if not args.sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_ID in .env or pass --sheet-id")

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    from descriptor_cloud_benchmark.monitoring.sheets import sync_results_and_complexity_tabs

    exp = args.experiment_id.strip() or None
    stats = sync_results_and_complexity_tabs(
        args.sheet_id,
        experiment_id=exp,
        metric=args.metric,
    )
    out = repo_root / "tmp" / "sheets_sync_stats.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
