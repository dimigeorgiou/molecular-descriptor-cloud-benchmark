#!/usr/bin/env python3
"""Inspect Chemoinformatics Reporter Google Sheet (Results + tab list)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Inspect Google Sheets Results tab.")
    parser.add_argument(
        "--sheet-id",
        default=os.getenv("GOOGLE_SHEETS_ID"),
        help="Spreadsheet ID (default: GOOGLE_SHEETS_ID from .env)",
    )
    parser.add_argument("--summary", action="store_true", help="Print row counts by experiment")
    parser.add_argument("--tabs", action="store_true", help="List worksheet titles")
    parser.add_argument("--limit", type=int, default=5, help="Sample rows to print")
    args = parser.parse_args()

    if not args.sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_ID in .env or pass --sheet-id")

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    from src.monitoring.sheets import _get_client, read_results_rows, summarize_results_rows

    gc = _get_client()
    sh = gc.open_by_key(args.sheet_id)

    if args.tabs:
        print("Worksheets:", [ws.title for ws in sh.worksheets()])

    rows = read_results_rows(args.sheet_id)
    print(f"Results rows (incl. header): {len(rows)}")

    if args.summary:
        summary = summarize_results_rows(rows)
        print(json.dumps(summary, indent=2))

    if rows:
        print("\nHeader:", rows[0])
        for row in rows[1 : 1 + args.limit]:
            print(row)


if __name__ == "__main__":
    main()
