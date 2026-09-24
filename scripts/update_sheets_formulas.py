#!/usr/bin/env python3
"""Push corrected QUERY formulas to Complexity_Low / Complexity_Medium tabs."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Update Google Sheets complexity pivot formulas."
    )
    parser.add_argument(
        "--sheet-id",
        default=os.getenv("GOOGLE_SHEETS_ID"),
        help="Spreadsheet ID (default: GOOGLE_SHEETS_ID)",
    )
    parser.add_argument(
        "--experiment-id",
        default=os.getenv("SHEETS_EXPERIMENT_FILTER", ""),
        help="Filter pivots to one experiment_id (recommended).",
    )
    args = parser.parse_args()

    if not args.sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_ID in .env or pass --sheet-id")

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    from src.monitoring.sheets import update_complexity_analysis_tabs

    exp = args.experiment_id.strip() or None
    update_complexity_analysis_tabs(args.sheet_id, experiment_id=exp)
    if exp:
        print(f"Updated Complexity_Low / Complexity_Medium formulas (experiment filter={exp})")
    else:
        print(
            "Updated Complexity_Low / Complexity_Medium formulas "
            "(low=paper_replication_low_compute_only, "
            "medium=paper_replication_medium_compute_only)"
        )


if __name__ == "__main__":
    main()
