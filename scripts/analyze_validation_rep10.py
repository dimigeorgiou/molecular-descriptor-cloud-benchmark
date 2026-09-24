#!/usr/bin/env python3
"""Summarize validation_rep10_* On-Demand runs from Sheets; recommend n_replicas for full grid."""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.core.replica_analysis import aggregate_replicas, coefficient_of_variation

EXPERIMENTS = [
    "validation_low_D5000_N25_rep10_ondemand",
    "validation_low_D5000_N50_rep10_ondemand",
    "validation_medium_D5000_N25_rep10_ondemand",
    "validation_medium_D5000_N50_rep10_ondemand",
]


def load_sheets(sheet_id: str) -> list[dict]:
    from dotenv import load_dotenv

    load_dotenv()
    from src.monitoring.sheets import read_results_rows

    raw = read_results_rows(sheet_id)
    if not raw:
        return []
    hdr = {h: i for i, h in enumerate(raw[0])}

    def col(row: list[str], name: str) -> str:
        i = hdr.get(name)
        return row[i] if i is not None and i < len(row) else ""

    rows: list[dict] = []
    for row in raw[1:]:
        exp = col(row, "Experiment ID")
        if exp not in EXPERIMENTS:
            continue
        notes = col(row, "Notes")
        replica_index = 0
        if "replica=" in notes:
            try:
                part = notes.split("replica=")[1].split("/")[0].split(";")[0].strip()
                replica_index = max(0, int(part) - 1)
            except (ValueError, IndexError):
                pass
        rows.append(
            {
                "experiment_id": exp,
                "mode": col(row, "Mode"),
                "dataset_size": int(col(row, "Dataset Size (D)") or 0),
                "n_nodes": int(col(row, "Nodes (N)") or 0),
                "cluster_init_sec": float(col(row, "Cluster Init (s)") or 0),
                "wall_clock_sec": float(col(row, "Wall Clock (s)") or 0),
                "computation_sec": float(col(row, "Computation (s)") or 0),
                "cost_usd": float(col(row, "Cost (USD)") or 0),
                "cost_spot_usd": float(col(row, "Cost Spot Equiv (USD)") or 0),
                "cost_ondemand_usd": float(col(row, "Cost On-Demand Equiv (USD)") or 0),
                "pricing_tier": col(row, "Pricing Tier"),
                "replica_index": replica_index,
                "notes": notes,
            }
        )
    return rows


def recommend_n(cv: float) -> int:
    if cv < 0.1:
        return 3
    if cv < 0.2:
        return 5
    return 10


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 4)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=REPO / "tmp" / "validation_rep10_report.json")
    args = p.parse_args()
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise SystemExit("GOOGLE_SHEETS_ID required")

    rows = load_sheets(sheet_id)
    report: dict = {
        "cells": [],
        "recommend_full_grid_n_replicas": {},
        "cost_summary": {},
        "correlations": {},
    }

    for exp in EXPERIMENTS:
        sub = [r for r in rows if r["experiment_id"] == exp]
        if not sub:
            report["cells"].append({"experiment_id": exp, "error": "no rows"})
            continue
        d, n = sub[0]["dataset_size"], sub[0]["n_nodes"]
        inits = [r["cluster_init_sec"] for r in sub]
        walls = [r["wall_clock_sec"] for r in sub]
        comps = [r["computation_sec"] for r in sub]
        costs = [r["cost_usd"] for r in sub]
        init_cv = coefficient_of_variation(inits) if len(inits) > 1 else 0.0
        wall_cv = coefficient_of_variation(walls) if len(walls) > 1 else 0.0
        order = [r["replica_index"] + 1 for r in sub]
        cell = {
            "experiment_id": exp,
            "D": d,
            "N": n,
            "n_replicas": len(sub),
            "cluster_init_sec": {
                "mean": round(statistics.mean(inits), 3),
                "stdev": round(statistics.stdev(inits), 3) if len(inits) > 1 else 0.0,
                "cv": round(init_cv, 4),
                "min": round(min(inits), 3),
                "max": round(max(inits), 3),
            },
            "wall_clock_sec": {
                "mean": round(statistics.mean(walls), 3),
                "stdev": round(statistics.stdev(walls), 3) if len(walls) > 1 else 0.0,
                "cv": round(wall_cv, 4),
            },
            "computation_sec_mean": round(statistics.mean(comps), 3),
            "cost_usd": {
                "mean": round(statistics.mean(costs), 4),
                "sum": round(sum(costs), 4),
                "stdev": round(statistics.stdev(costs), 4) if len(costs) > 1 else 0.0,
            },
            "corr_replica_order_init": _pearson(
                [float(o) for o in order], inits
            ),
            "recommended_n_replicas": recommend_n(max(init_cv, wall_cv)),
        }
        complexity = "medium" if "medium" in exp else "low"
        report["recommend_full_grid_n_replicas"][complexity] = max(
            report["recommend_full_grid_n_replicas"].get(complexity, 3),
            cell["recommended_n_replicas"],
        )
        report["cells"].append(cell)

    all_costs = [r["cost_usd"] for r in rows if r["cost_usd"] > 0]
    all_inits = [r["cluster_init_sec"] for r in rows]
    all_walls = [r["wall_clock_sec"] for r in rows]
    report["cost_summary"] = {
        "total_usd": round(sum(all_costs), 2),
        "mean_per_job_usd": round(statistics.mean(all_costs), 4) if all_costs else 0,
        "n_jobs": len(all_costs),
    }
    report["correlations"] = {
        "init_vs_wall_clock": _pearson(all_inits, all_walls),
        "init_vs_cost": _pearson(all_inits, all_costs) if len(all_costs) == len(all_inits) else None,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
