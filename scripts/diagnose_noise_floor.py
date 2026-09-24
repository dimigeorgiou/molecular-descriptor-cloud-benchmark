#!/usr/bin/env python3
"""
Noise-floor diagnostic for benchmarking replication studies.

Given Results sheet rows or local JSON, finds (D,N) cells with >=2 runs and compares:
  - run-to-run CV of wall_clock_sec (replica noise)
  - across-N range of per-cell medians at fixed D (U-curve signal)

Flags D values where replica noise range exceeds across-N signal range.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from descriptor_cloud_benchmark.core.replica_analysis import aggregate_replicas, coefficient_of_variation


def _wall_from_row(row: dict) -> float:
    wall = row.get("wall_clock_sec")
    if wall is not None:
        return float(wall)
    s3 = float(row.get("s3_upload_sec") or 0)
    init = float(row.get("cluster_init_sec") or 0)
    par = float(row.get("cluster_parallel_sec") or 0)
    total = float(row.get("total_pipeline_sec") or 0)
    if not par and total:
        par = max(total - s3, 0.0)
    return s3 + init + par


def _wall_from_sheet_row(hdr: dict[str, int], row: list[str]) -> float:
    def col(name: str, default: float = 0.0) -> float:
        i = hdr.get(name)
        if i is None or i >= len(row) or row[i] == "":
            return default
        return float(row[i])

    w = col("Wall Clock (s)", 0.0)
    if w:
        return w
    s3 = col("S3 Upload (s)")
    init = col("Cluster Init (s)")
    par = col("Cluster Parallel (s)")
    total = col("Total Pipeline (s)")
    if not par and total:
        par = max(total - s3, 0.0)
    return s3 + init + par


def load_rows_from_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "runs" in data:
        return data["runs"]
    raise ValueError(f"Unsupported JSON shape: {path}")


def load_rows_from_sheets(sheet_id: str) -> list[dict]:
    from dotenv import load_dotenv

    load_dotenv()
    from descriptor_cloud_benchmark.monitoring.sheets import read_results_rows

    rows = read_results_rows(sheet_id)
    if not rows:
        return []
    hdr = {h: i for i, h in enumerate(rows[0])}
    out: list[dict] = []
    for row in rows[1:]:
        if len(row) <= hdr.get("Dataset Size (D)", 3):
            continue
        out.append(
            {
                "experiment_id": row[hdr["Experiment ID"]],
                "mode": row[hdr["Mode"]],
                "dataset_size": int(float(row[hdr["Dataset Size (D)"]])),
                "n_nodes": int(float(row[hdr["Nodes (N)"]])),
                "status": row[hdr["Status"]] if "Status" in hdr else "",
                "wall_clock_sec": _wall_from_sheet_row(hdr, row),
                "notes": row[hdr["Notes"]] if "Notes" in hdr else "",
            }
        )
    return out


def diagnose(
    rows: list[dict],
    *,
    experiment_id: str | None = None,
    mode: str | None = "compute_only",
    succeeded_only: bool = True,
) -> dict:
    filtered: list[dict] = []
    for r in rows:
        if experiment_id and r.get("experiment_id") != experiment_id:
            continue
        if mode and r.get("mode") != mode:
            continue
        if succeeded_only and r.get("status") not in ("SUCCEEDED", "completed", ""):
            continue
        filtered.append(r)

    by_cell: dict[tuple[int, int], list[float]] = defaultdict(list)
    for r in filtered:
        d = int(r["dataset_size"])
        n = int(r["n_nodes"])
        by_cell[(d, n)].append(_wall_from_row(r))

    multi_run: list[dict] = []
    for (d, n), walls in sorted(by_cell.items()):
        if len(walls) < 2:
            continue
        cv = coefficient_of_variation(walls)
        multi_run.append(
            {
                "D": d,
                "N": n,
                "n_runs": len(walls),
                "wall_values": [round(w, 3) for w in walls],
                "cv": round(cv, 4),
                "range": round(max(walls) - min(walls), 3),
            }
        )

    agg = aggregate_replicas(filtered)
    by_d: dict[int, dict[int, float]] = defaultdict(dict)
    for key, stats in agg.items():
        _exp, _mode, d, n = key
        by_d[int(d)][int(n)] = float(stats["median_wall_clock"])

    flagged_d: list[dict] = []
    for d in sorted(by_d):
        medians = list(by_d[d].values())
        if len(medians) < 2:
            continue
        signal_range = max(medians) - min(medians)
        cell_noise = [x["range"] for x in multi_run if x["D"] == d]
        max_noise_range = max(cell_noise) if cell_noise else 0.0
        max_cv = max(
            (x["cv"] for x in multi_run if x["D"] == d),
            default=0.0,
        )
        noise_dominated = max_noise_range > signal_range
        flagged_d.append(
            {
                "D": d,
                "across_N_median_range_sec": round(signal_range, 3),
                "max_replica_range_sec": round(max_noise_range, 3),
                "max_replica_cv": round(max_cv, 4),
                "noise_dominated": noise_dominated,
            }
        )

    return {
        "n_rows": len(filtered),
        "multi_run_cells": multi_run,
        "by_D_summary": flagged_d,
        "noise_dominated_D": [x["D"] for x in flagged_d if x["noise_dominated"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Local results JSON (list of rows)")
    parser.add_argument("--sheet-id", type=str, default=os.getenv("GOOGLE_SHEETS_ID"))
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--mode", type=str, default="compute_only")
    parser.add_argument("--out", type=Path, default=REPO / "tmp" / "noise_floor_report.json")
    args = parser.parse_args()

    if args.json:
        rows = load_rows_from_json(args.json)
    elif args.sheet_id:
        rows = load_rows_from_sheets(args.sheet_id)
    else:
        raise SystemExit("Provide --json or set GOOGLE_SHEETS_ID")

    report = diagnose(
        rows,
        experiment_id=args.experiment_id,
        mode=args.mode,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))

    print(f"Rows analyzed: {report['n_rows']}")
    print(f"Cells with >=2 runs: {len(report['multi_run_cells'])}")
    for cell in report["multi_run_cells"]:
        print(
            f"  D={cell['D']} N={cell['N']}: n={cell['n_runs']} "
            f"CV={cell['cv']:.3f} range={cell['range']}s walls={cell['wall_values']}"
        )
    print("\nBy-D noise vs signal:")
    for row in report["by_D_summary"]:
        flag = "NOISE-DOMINATED" if row["noise_dominated"] else "ok"
        print(
            f"  D={row['D']}: signal_range={row['across_N_median_range_sec']}s "
            f"max_replica_range={row['max_replica_range_sec']}s → {flag}"
        )
    if report["noise_dominated_D"]:
        print(f"\nFlagged D values: {report['noise_dominated_D']}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
