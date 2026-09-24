#!/usr/bin/env python3
"""
Compare cluster_init_sec variance: Spot vs On-Demand pilot (or historical rows).

Epistemic status: a large CV drop on On-Demand supports the Spot-noise hypothesis;
it does not prove causation (AZ variance, clock skew, cold-start baseline remain confounds).

Usage (after pilot runs land in Sheets):
  PYTHONPATH=. python scripts/compare_spot_vs_ondemand_init.py

  PYTHONPATH=. python scripts/compare_spot_vs_ondemand_init.py \\
    --spot-experiment pilot_spot_D5000_N25_rep3 \\
    --ondemand-experiment pilot_ondemand_D5000_N25_rep3 \\
    --d 5000 --n 25
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from statistics import mean, stdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.core.replica_analysis import coefficient_of_variation


def _pearson_r(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Return (r, two-tailed p) via t approximation; p=nan if n<3."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return float("nan"), float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return float("nan"), float("nan")
    r = num / (den_x * den_y)
    if abs(r) >= 1:
        return r, 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    # two-tailed p from t CDF approximation (rough; adequate for n~20)
    from math import erf, sqrt

    def t_cdf(t_val: float, df: int) -> float:
        x = df / (df + t_val * t_val)
        # regularized incomplete beta — use scipy-free rough tail
        return 0.5 + 0.5 * erf(t_val / sqrt(2)) if df > 30 else 0.5 + 0.5 * math.tanh(t_val / 2)

    p = 2 * (1 - t_cdf(abs(t), n - 2))
    return r, min(1.0, max(0.0, p))


def load_sheet_rows(sheet_id: str) -> list[dict]:
    from dotenv import load_dotenv

    load_dotenv()
    from src.monitoring.sheets import read_results_rows

    raw = read_results_rows(sheet_id)
    if not raw:
        return []
    hdr = {h: i for i, h in enumerate(raw[0])}

    def col(row: list[str], name: str, default: str = "") -> str:
        i = hdr.get(name)
        if i is None or i >= len(row):
            return default
        return row[i]

    out: list[dict] = []
    for row in raw[1:]:
        try:
            out.append(
                {
                    "experiment_id": col(row, "Experiment ID"),
                    "mode": col(row, "Mode"),
                    "dataset_size": int(float(col(row, "Dataset Size (D)", "0") or 0)),
                    "n_nodes": int(float(col(row, "Nodes (N)", "0") or 0)),
                    "status": col(row, "Status"),
                    "cluster_init_sec": float(col(row, "Cluster Init (s)", "0") or 0),
                    "wall_clock_sec": float(col(row, "Wall Clock (s)", "0") or 0),
                    "notes": col(row, "Notes"),
                    "timestamp": col(row, "Timestamp (UTC)"),
                }
            )
        except (ValueError, TypeError):
            continue
    return out


def filter_cell(
    rows: list[dict],
    *,
    experiment_id: str | None,
    d: int,
    n: int,
    succeeded_only: bool = True,
) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if experiment_id and r.get("experiment_id") != experiment_id:
            continue
        if int(r.get("dataset_size", 0)) != d or int(r.get("n_nodes", 0)) != n:
            continue
        if succeeded_only and r.get("status") not in ("SUCCEEDED", "completed", ""):
            continue
        out.append(r)
    return out


def summarize_tier(label: str, rows: list[dict]) -> dict:
    inits = [float(r["cluster_init_sec"]) for r in rows]
    walls = [float(r["wall_clock_sec"]) for r in rows]
    orders = list(range(len(rows)))
    ns = [float(r["n_nodes"]) for r in rows]

    def stats(vals: list[float]) -> dict:
        if not vals:
            return {"n": 0, "mean": None, "stdev": None, "cv": None, "values": []}
        cv = coefficient_of_variation(vals) if len(vals) >= 2 else 0.0
        return {
            "n": len(vals),
            "mean": round(mean(vals), 3),
            "stdev": round(stdev(vals), 3) if len(vals) >= 2 else 0.0,
            "cv": round(cv, 4),
            "values": [round(v, 3) for v in vals],
        }

    r_n_init, p_n_init = _pearson_r(ns, inits) if len(rows) >= 3 else (float("nan"), float("nan"))
    r_ord_init, p_ord_init = (
        _pearson_r([float(x) for x in orders], inits) if len(rows) >= 3 else (float("nan"), float("nan"))
    )
    r_n_wall, p_n_wall = _pearson_r(ns, walls) if len(rows) >= 3 else (float("nan"), float("nan"))

    init_share = (
        round(mean(inits) / mean(walls), 4) if walls and mean(walls) > 0 else None
    )

    return {
        "tier": label,
        "n_rows": len(rows),
        "cluster_init_sec": stats(inits),
        "wall_clock_sec": stats(walls),
        "init_fraction_of_wall_mean": init_share,
        "corr_N_init": {"r": round(r_n_init, 3), "p": round(p_n_init, 3)},
        "corr_order_init": {"r": round(r_ord_init, 3), "p": round(p_ord_init, 3)},
        "corr_N_wall": {"r": round(r_n_wall, 3), "p": round(p_n_wall, 3)},
    }


def verdict(spot: dict, ondemand: dict) -> dict:
    spot_cv = spot["cluster_init_sec"]["cv"]
    od_cv = ondemand["cluster_init_sec"]["cv"]
    if spot_cv is None or od_cv is None:
        return {"verdict": "insufficient_data", "detail": "Need SUCCEEDED rows in both tiers."}
    ratio = spot_cv / od_cv if od_cv > 0 else float("inf")
    supports = od_cv < 0.25 and spot_cv > 0.4 and ratio >= 2
    return {
        "spot_init_cv": spot_cv,
        "ondemand_init_cv": od_cv,
        "cv_ratio_spot_over_ondemand": round(ratio, 2),
        "supports_spot_noise_hypothesis": supports,
        "interpretation": (
            "On-Demand init CV materially lower than Spot — consistent with Spot capacity noise."
            if supports
            else "Inconclusive: need both tiers with n≥3 SUCCEEDED replicas same day."
        ),
        "caveat": (
            "Consistency ≠ causation. AZ variance, submit_ts clock skew, and baseline "
            "cold-start on On-Demand are not ruled out."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-id", default=os.getenv("GOOGLE_SHEETS_ID"))
    parser.add_argument("--spot-experiment", default="pilot_spot_D5000_N25_rep3")
    parser.add_argument("--ondemand-experiment", default="pilot_ondemand_D5000_N25_rep3")
    parser.add_argument("--historical-spot-experiment", default=None, help="Optional prior Spot grid id")
    parser.add_argument("--d", type=int, default=5000)
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--out", type=Path, default=REPO / "tmp" / "spot_vs_ondemand_init.json")
    args = parser.parse_args()

    if not args.sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_ID or pass --sheet-id")

    all_rows = load_sheet_rows(args.sheet_id)
    spot_rows = filter_cell(
        all_rows, experiment_id=args.spot_experiment, d=args.d, n=args.n
    )
    od_rows = filter_cell(
        all_rows, experiment_id=args.ondemand_experiment, d=args.d, n=args.n
    )
    hist_rows: list[dict] = []
    if args.historical_spot_experiment:
        hist_rows = filter_cell(
            all_rows, experiment_id=args.historical_spot_experiment, d=args.d, n=args.n
        )

    report = {
        "cell": {"D": args.d, "N": args.n},
        "spot_pilot": summarize_tier("spot_pilot", spot_rows),
        "ondemand_pilot": summarize_tier("ondemand_pilot", od_rows),
        "historical_spot": summarize_tier("historical_spot", hist_rows) if hist_rows else None,
        "comparison": verdict(
            summarize_tier("spot_pilot", spot_rows),
            summarize_tier("ondemand_pilot", od_rows),
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))

    print(f"Cell D={args.d} N={args.n}")
    for key in ("spot_pilot", "ondemand_pilot"):
        block = report[key]
        init = block["cluster_init_sec"]
        print(
            f"  {key}: n={init['n']} init mean={init['mean']}s CV={init['cv']} "
            f"values={init['values']}"
        )
    cmp_ = report["comparison"]
    print(f"\n{cmp_['interpretation']}")
    print(f"  spot CV={cmp_.get('spot_init_cv')} ondemand CV={cmp_.get('ondemand_init_cv')} "
          f"ratio={cmp_.get('cv_ratio_spot_over_ondemand')}")
    print(f"  Caveat: {cmp_['caveat']}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
