#!/usr/bin/env python3
"""
Confirm Task 3 fit unit and refit time models on raw replicate rows (N≤185).

Previous Task 3 (paper2_tasks3_5_n185.py) fit on per-cell medians (42 points/tier).
This script:
  1) Documents that fact from the saved JSON.
  2) Refits the same candidate models on raw full_pipeline rows in cells with ≥3 reps.
  3) Reports row-wise LOOCV and leave-one-cell-out LOOCV (honest for config prediction).

Does not touch manuscript.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from scripts.paper2_tasks3_5_n185 import (
    CORE_D,
    CORE_N,
    MODELS,
    OUT,
    empirical_argmin,
    fit,
    loocv_metrics,
    pool_cells,
    predict_time,
)

FIGS = OUT / "figs"


def _pf(x: Any) -> float | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(x)
    except Exception:
        return None


def load_rows(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def eligible_cells(rows: list[dict], cx: str, metric: str, min_reps: int = 3) -> set[tuple[int, int]]:
    buckets: dict[tuple[int, int], int] = defaultdict(int)
    for r in rows:
        if r.get("ModeNorm") != "full_pipeline" or r.get("Complexity") != cx:
            continue
        try:
            D, N = int(r["D"]), int(r["N"])
        except Exception:
            continue
        if D not in CORE_D or N not in CORE_N or N > 185:
            continue
        y = _pf(r.get(metric))
        if y is None or y <= 0:
            continue
        buckets[(D, N)] += 1
    return {k for k, n in buckets.items() if n >= min_reps}


def pool_raw_rows(
    rows: list[dict],
    *,
    cx: str,
    metric: str,
    min_reps: int = 3,
) -> list[tuple[int, int, float]]:
    """Return (D, N, y) for every replicate in eligible cells (≥min_reps)."""
    ok = eligible_cells(rows, cx, metric, min_reps)
    out: list[tuple[int, int, float]] = []
    for r in rows:
        if r.get("ModeNorm") != "full_pipeline" or r.get("Complexity") != cx:
            continue
        try:
            D, N = int(r["D"]), int(r["N"])
        except Exception:
            continue
        if (D, N) not in ok:
            continue
        y = _pf(r.get(metric))
        if y is None or y <= 0:
            continue
        out.append((D, N, float(y)))
    return out


def leave_one_cell_out(X: np.ndarray, y: np.ndarray, cell_ids: np.ndarray) -> tuple[float, float]:
    """LOOCV where each held-out unit is a (D,N) cell (all its replicates)."""
    preds = np.zeros(len(y))
    for cid in np.unique(cell_ids):
        m = cell_ids != cid
        beta, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
        preds[cell_ids == cid] = X[cell_ids == cid] @ beta
    ss_res = float(np.sum((y - preds) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(np.mean((y - preds) ** 2)))
    return rmse, r2


def evaluate_raw(points: list[tuple[int, int, float]]) -> dict[str, Any]:
    D = np.array([p[0] for p in points], float)
    N = np.array([p[1] for p in points], float)
    y = np.array([p[2] for p in points], float)
    # Stable cell id for leave-one-cell-out
    cell_key = {(int(d), int(n)): i for i, (d, n) in enumerate(sorted(set(zip(D.astype(int), N.astype(int)))))}
    cell_ids = np.array([cell_key[(int(d), int(n))] for d, n in zip(D, N)])

    results = {}
    for name, (coeff_names, design) in MODELS.items():
        X = design(N, D)
        beta, r2, aic = fit(X, y)
        rmse_row, r2_loo_row = loocv_metrics(X, y)
        rmse_cell, r2_loo_cell = leave_one_cell_out(X, y, cell_ids)
        coeffs = {k: float(v) for k, v in zip(coeff_names, beta)}
        d_curv = coeffs.get("d")
        results[name] = {
            "coeffs": coeffs,
            "r2_in_sample": r2,
            "r2_loocv_row": r2_loo_row,
            "loocv_rmse_row": rmse_row,
            "r2_loocv_cell": r2_loo_cell,
            "loocv_rmse_cell": rmse_cell,
            "aic": aic,
            "n_params": len(coeff_names),
            "curvature_d_positive": (d_curv is not None and d_curv > 0)
            if name == "quadratic"
            else None,
        }

    # Rank by leave-one-cell-out R² (primary honest metric); tiebreak AIC
    ranked = sorted(results.items(), key=lambda kv: (-kv[1]["r2_loocv_cell"], kv[1]["aic"]))
    winner_name, winner = ranked[0]
    return {
        "n_rows": len(points),
        "n_cells": len(set((p[0], p[1]) for p in points)),
        "models": results,
        "winner_by_cell_loocv": winner_name,
        "winner_detail": winner,
        "ranking_by_cell_loocv": [n for n, _ in ranked],
        "ranking_by_row_loocv": [
            n
            for n, _ in sorted(results.items(), key=lambda kv: (-kv[1]["r2_loocv_row"], kv[1]["aic"]))
        ],
    }


def emp_argmin_from_medians(rows: list[dict], cx: str, metric: str) -> dict[str, Any]:
    med_pts = pool_cells(rows, cx=cx, metric=metric, min_reps=3, max_n=185)
    return empirical_argmin(med_pts)


def selector_boundary_check(block: dict[str, Any], cx: str) -> dict[str, Any]:
    """For each D, does predicted T decrease as N grows from 25→185?"""
    name = block["winner_by_cell_loocv"]
    coeffs = block["winner_detail"]["coeffs"]
    out = {}
    for D in CORE_D:
        preds = [(N, predict_time(name, coeffs, float(N), float(D))) for N in CORE_N]
        n_star = min(preds, key=lambda t: t[1])[0]
        out[str(D)] = {
            "N_star_pred": int(n_star),
            "T_pred_at_Nstar": float(min(preds, key=lambda t: t[1])[1]),
            "T_pred_N25": float(preds[0][1]),
            "T_pred_N185": float(preds[-1][1]),
            "boundary_min_is_N25": n_star == 25,
        }
    return out


def main() -> None:
    csv_path = OUT / "corrected_sheet_succeeded.csv"
    prior = json.loads((OUT / "task3_time_models_nle185.json").read_text())
    rows = load_rows(csv_path)

    prior_n = {
        cx: prior[cx]["RealWallClock"]["n_cells"]
        for cx in ("low", "medium")
        if cx in prior and "RealWallClock" in prior[cx]
    }

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnosis": {
            "prior_task3_fit_unit": "per-cell medians",
            "prior_n_cells": prior_n,
            "evidence": (
                "scripts/paper2_tasks3_5_n185.py pool_cells() appends "
                "np.median(vals); task3 JSON reports n_cells=42"
            ),
            "hypothesis_confirmed": True,
        },
        "refit_unit": "raw replicate rows in cells with >=3 reps, N<=185, full_pipeline",
        "tiers": {},
    }

    lines = [
        "# Task 3 — medians vs raw-row refit\n",
        f"Generated: `{report['generated_at']}`\n\n",
        "## Diagnosis\n",
        "- **Prior Task 3 fit unit: per-cell medians** (`n_cells=42` per tier).\n",
        "- Code: `pool_cells()` → `np.median(vals)` then `evaluate_models`.\n",
        "- Hypothesis confirmed: weak R²/LOOCV was measured on 42 aggregated points, not raw rows.\n\n",
        "## Raw-row refit (same model zoo, N≤185, ≥3-rep cells)\n",
        "- Primary selection metric: **leave-one-cell-out R²** (predict held-out (D,N) cells).\n",
        "- Also report row-wise LOOCV (can look optimistic because replicates share (D,N)).\n\n",
    ]

    for cx in ("low", "medium"):
        pts = pool_raw_rows(rows, cx=cx, metric="RealWallClock", min_reps=3)
        block = evaluate_raw(pts)
        emp = emp_argmin_from_medians(rows, cx, "RealWallClock")
        boundary = selector_boundary_check(block, cx)
        prior_w = prior[cx]["RealWallClock"]["winner_detail"]
        report["tiers"][cx] = {
            "prior_median_fit": {
                "winner": prior[cx]["RealWallClock"]["winner"],
                "n_cells": prior[cx]["RealWallClock"]["n_cells"],
                "r2_in_sample": prior_w["r2_in_sample"],
                "r2_loocv": prior_w["r2_loocv"],
                "aic": prior_w["aic"],
            },
            "raw_row_fit": block,
            "empirical_argmin_on_cell_medians": emp,
            "predicted_Nstar_boundary": boundary,
            "reversal_flag": {
                "N_at_D5000": emp["5000"]["N_emp_min"],
                "N_at_D50000": emp["50000"]["N_emp_min"],
                "delta": emp["50000"]["N_emp_min"] - emp["5000"]["N_emp_min"],
                "reversal_persists": emp["50000"]["N_emp_min"] < emp["5000"]["N_emp_min"],
            },
        }

        w = block["winner_detail"]
        lines.append(f"### {cx}\n")
        lines.append(
            f"- Prior (medians, n={prior_n[cx]}): winner=`{prior[cx]['RealWallClock']['winner']}` "
            f"R²={prior_w['r2_in_sample']:.3f} LOOCV-R²={prior_w['r2_loocv']:.3f}\n"
        )
        lines.append(
            f"- Raw rows: n_rows={block['n_rows']} n_cells={block['n_cells']}; "
            f"winner_by_cell_LOOCV=`{block['winner_by_cell_loocv']}`\n"
        )
        lines.append(
            f"  - in-sample R²={w['r2_in_sample']:.3f}; "
            f"row-LOOCV R²={w['r2_loocv_row']:.3f}; "
            f"**cell-LOOCV R²={w['r2_loocv_cell']:.3f}**; AIC={w['aic']:.1f}\n"
        )
        n25_count = sum(1 for v in boundary.values() if v["boundary_min_is_N25"])
        lines.append(
            f"- Predicted N* at boundary N=25 for {n25_count}/{len(boundary)} D values "
            f"(winner coeffs).\n"
        )
        lines.append(f"- Emp argmin (cell medians): `{emp}`\n")
        lines.append(
            f"- Reversal flag: `{report['tiers'][cx]['reversal_flag']}`\n\n"
        )

        # All models compact table
        lines.append("| model | R² | row-LOOCV | cell-LOOCV | AIC |\n")
        lines.append("|---|---:|---:|---:|---:|\n")
        for name in block["ranking_by_cell_loocv"]:
            m = block["models"][name]
            lines.append(
                f"| `{name}` | {m['r2_in_sample']:.3f} | {m['r2_loocv_row']:.3f} | "
                f"{m['r2_loocv_cell']:.3f} | {m['aic']:.1f} |\n"
            )
        lines.append("\n")

    # Framing recommendation
    med_neg = any(
        report["tiers"][cx]["raw_row_fit"]["winner_detail"]["r2_loocv_cell"] < 0
        for cx in ("low", "medium")
    )
    weak = any(
        report["tiers"][cx]["raw_row_fit"]["winner_detail"]["r2_loocv_cell"] < 0.2
        for cx in ("low", "medium")
    )
    report["manuscript_recommendation"] = {
        "do_not_quote_Nstar_from_parametric_fit": med_neg or weak,
        "preferred_framing": (
            "no interior time-minimizing configuration in tested N=25..185; "
            "smallest tested N at/near optimal; scheduling overhead dominates"
            if (med_neg or weak)
            else "parametric N*(D) may be usable after further review"
        ),
        "use_task4_cost_model": True,
        "use_task1_od_spot_ratio_3_20": True,
        "note": (
            "If cell-LOOCV R² stays near zero/negative after raw-row refit, "
            "put negative/weak LOOCV in Limitations; do not publish N* table from the fit."
        ),
    }

    lines.append("## Manuscript recommendation\n")
    lines.append(f"- `{json.dumps(report['manuscript_recommendation'], indent=2)}`\n")

    out_json = OUT / "task3_time_models_raw_rows_nle185.json"
    out_md = OUT / "TASK3_MEDIANS_VS_RAW_REFIT.md"
    out_json.write_text(json.dumps(report, indent=2))
    out_md.write_text("".join(lines))
    print(out_md.read_text())
    print(f"\nWrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
