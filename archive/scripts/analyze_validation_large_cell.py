#!/usr/bin/env python3
"""Compare estimator vs actual for large-cell validation (D=50000, N=185, rep5)."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from experiments.estimator.experiment_estimator import estimate_config, load_model
from experiments.verify_estimate_vs_actual import compare_runs

EXPERIMENTS = [
    "validation_large_low_D50000_N185_rep5_ondemand",
    "validation_large_medium_D50000_N185_rep5_ondemand",
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
                "dataset_size": int(col(row, "Dataset Size (D)") or 0),
                "n_nodes": int(col(row, "Nodes (N)") or 0),
                "computation_sec": float(col(row, "Computation (s)") or 0),
                "total_pipeline_sec": float(col(row, "Total Pipeline (s)") or 0),
                "wall_clock_sec": float(col(row, "Wall Clock (s)") or 0),
                "cluster_init_sec": float(col(row, "Cluster Init (s)") or 0),
                "cost_usd": float(col(row, "Cost (USD)") or 0),
                "cost_spot_usd": float(col(row, "Cost Spot Equiv (USD)") or 0),
                "cost_ondemand_usd": float(col(row, "Cost On-Demand Equiv (USD)") or 0),
                "replica_index": replica_index,
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out",
        type=Path,
        default=REPO / "tmp" / "validation_large_D50000_N185_report.json",
    )
    args = p.parse_args()
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise SystemExit("GOOGLE_SHEETS_ID required")

    model = load_model(None)
    actual_rows = load_sheets(sheet_id)
    report: dict = {"cells": [], "full_grid_extrapolation": {}}

    for exp in EXPERIMENTS:
        sub = [r for r in actual_rows if r["experiment_id"] == exp]
        complexity = "medium" if "medium" in exp else "low"
        est_one = estimate_config(
            185,
            50000,
            model,
            vcpus_per_node=4,
            gb_per_node=8,
            use_spot=False,
            smiles_complexity=complexity,
            mode="compute_only",
            n_replicas=1,
            n_grid_cells=1,
        )
        est_five = {k: round(v * 5, 4) if k.endswith("_usd") else v for k, v in est_one.items()}
        if sub:
            costs = [r["cost_usd"] for r in sub]
            comps = [r["computation_sec"] for r in sub]
            walls = [r["wall_clock_sec"] for r in sub]
            actual_agg = {
                "n_replicas": len(sub),
                "cost_usd_sum": round(sum(costs), 4),
                "cost_usd_mean": round(statistics.mean(costs), 4),
                "computation_sec_mean": round(statistics.mean(comps), 3),
                "wall_clock_sec_mean": round(statistics.mean(walls), 3),
            }
            compare = compare_runs(
                {"per_config": [est_one], "mode": "compute_only"},
                sub,
                metric="cost_usd",
            )
            compare_comp = compare_runs(
                {"per_config": [est_one], "mode": "compute_only"},
                sub,
                metric="computation_sec",
            )
        else:
            actual_agg = {"error": "no rows in Sheets yet"}
            compare = {}
            compare_comp = {}

        cell = {
            "experiment_id": exp,
            "complexity": complexity,
            "D": 50000,
            "N": 185,
            "estimate_per_replica": est_one,
            "estimate_5_replicas": {
                "estimated_cost_usd": round(est_one["estimated_cost_usd"] * 5, 4),
                "estimated_cost_spot_usd": round(est_one["estimated_cost_spot_usd"] * 5, 4),
                "estimated_cost_ondemand_usd": round(
                    est_one["estimated_cost_ondemand_usd"] * 5, 4
                ),
                "computation_sec": est_one["computation_sec"],
            },
            "actual": actual_agg,
            "cost_compare": compare,
            "computation_compare": compare_comp,
        }
        report["cells"].append(cell)

    # Extrapolate: if full grid @10 reps OD ~= $1781, what fraction is this cell?
    if len(report["cells"]) == 2 and all("cost_usd_sum" in c.get("actual", {}) for c in report["cells"]):
        actual_both = sum(c["actual"]["cost_usd_sum"] for c in report["cells"])
        est_both = sum(c["estimate_5_replicas"]["estimated_cost_ondemand_usd"] for c in report["cells"])
        ratio = actual_both / est_both if est_both else None
        proj_path = REPO / "tmp" / "full_pipeline_cost_projection.json"
        projected_od_10 = None
        if proj_path.exists():
            proj = json.loads(proj_path.read_text())
            projected_od_10 = proj.get("combined_recommended", {}).get("on_demand_usd")
        report["full_grid_extrapolation"] = {
            "actual_10_runs_usd": round(actual_both, 2),
            "estimated_10_runs_usd": round(est_both, 2),
            "actual_to_estimate_ratio": round(ratio, 3) if ratio else None,
            "projected_full_grid_od_10_reps_usd": projected_od_10,
            "revised_full_grid_od_if_linear": round(projected_od_10 * ratio, 2)
            if projected_od_10 and ratio
            else None,
            "note": (
                "Linear scaling: multiply $1781 projection by actual/estimate ratio from "
                "these 10 large-cell runs (rough; ignores other D,N mix)."
            ),
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
