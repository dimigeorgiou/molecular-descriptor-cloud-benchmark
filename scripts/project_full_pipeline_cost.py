#!/usr/bin/env python3
"""
Project full paper-replication grid cost (low + medium) using improved estimator.

Writes tmp/full_pipeline_cost_projection.json with Spot and On-Demand totals at
several n_replicas scenarios. After validation, pass --validation-report to
blend empirical cost multipliers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from experiments.estimator.experiment_estimator import load_config, load_model, run_estimator

CONFIGS = [
    REPO / "experiments/configs/paper_replication_low_compute_only.yaml",
    REPO / "experiments/configs/paper_replication_medium_compute_only.yaml",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--validation-report",
        type=Path,
        default=None,
        help="tmp/validation_rep10_report.json for empirical n_replicas",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=REPO / "tmp" / "full_pipeline_cost_projection.json",
    )
    p.add_argument("--dataset-dir", type=Path, default=REPO / "datasets" / "samples")
    args = p.parse_args()

    model = load_model(None)
    scenarios: dict[str, dict] = {}
    rep_by_complexity = {"low": 3, "medium": 3}
    if args.validation_report and args.validation_report.exists():
        vr = json.loads(args.validation_report.read_text())
        rep_by_complexity = vr.get("recommend_full_grid_n_replicas", rep_by_complexity)

    for cfg_path in CONFIGS:
        cfg = load_config(cfg_path)
        complexity = cfg.get("smiles_complexity", "medium")
        for use_spot, label in ((True, "spot"), (False, "on_demand")):
            for n_rep in (3, 5, 10, rep_by_complexity.get(complexity, 3)):
                run_cfg = dict(cfg)
                run_cfg["use_spot"] = use_spot
                run_cfg["n_replicas"] = n_rep
                summary = run_estimator(
                    run_cfg,
                    model,
                    dataset_dir=args.dataset_dir,
                )
                key = f"{complexity}_{label}_rep{n_rep}"
                scenarios[key] = {
                    "config": str(cfg_path.name),
                    "complexity": complexity,
                    "use_spot": use_spot,
                    "n_replicas": n_rep,
                    "n_jobs": summary["n_jobs"],
                    "total_time_hours": summary["total_time_hours"],
                    "total_cost_usd": summary["total_cost_usd"],
                    "total_cost_spot_usd": summary.get("total_cost_spot_usd"),
                    "total_cost_ondemand_usd": summary.get("total_cost_ondemand_usd"),
                }

    recommended = {
        "low": {
            "n_replicas": rep_by_complexity.get("low", 3),
            "spot_usd": scenarios.get(
                f"low_spot_rep{rep_by_complexity.get('low', 3)}", {}
            ).get("total_cost_usd"),
            "on_demand_usd": scenarios.get(
                f"low_on_demand_rep{rep_by_complexity.get('low', 3)}", {}
            ).get("total_cost_usd"),
        },
        "medium": {
            "n_replicas": rep_by_complexity.get("medium", 3),
            "spot_usd": scenarios.get(
                f"medium_spot_rep{rep_by_complexity.get('medium', 3)}", {}
            ).get("total_cost_usd"),
            "on_demand_usd": scenarios.get(
                f"medium_on_demand_rep{rep_by_complexity.get('medium', 3)}", {}
            ).get("total_cost_usd"),
        },
    }
    combined_spot = (recommended["low"].get("spot_usd") or 0) + (
        recommended["medium"].get("spot_usd") or 0
    )
    combined_od = (recommended["low"].get("on_demand_usd") or 0) + (
        recommended["medium"].get("on_demand_usd") or 0
    )

    out = {
        "scenarios": scenarios,
        "recommended_after_validation": recommended,
        "combined_recommended": {
            "spot_usd": round(combined_spot, 2),
            "on_demand_usd": round(combined_od, 2),
        },
        "notes": (
            "Costs from estimator with warm-CE cluster_init (55s) and dual Spot/OD rates. "
            "Actual Batch billing uses child job vCPU×runtime from describe_jobs."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
