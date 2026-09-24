#!/usr/bin/env python3
"""
Paper 2 Tasks 3–5 — N≤185 only (post core top-up).

- Excludes N>185 from all fitted models (unreplicated; optional illustrative plot only).
- Requires ≥3 replicates per (complexity, D, N) cell for model fits.
- Does not touch .tex / manuscript.

Usage:
  PYTHONPATH=. python scripts/paper2_tasks3_5_n185.py
  PYTHONPATH=. python scripts/paper2_tasks3_5_n185.py --refresh-sheet
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env")

OUT = REPO / "tmp" / "paper2_rebuild"
FIGS = OUT / "figs"
CORE_D = (5000, 10000, 20000, 30000, 40000, 50000)
CORE_N = (25, 50, 75, 100, 125, 150, 185)

# Candidate models: name -> (n_params, design_fn)
ModelFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


def design_quadratic(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(N), N, D, N**2, N * D])


def design_dn_sqrt(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(N), D / N, np.sqrt(N)])


def design_dn_N(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(N), D / N, N])


def design_dn_log(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(N), D / N, np.log(N)])


def design_dn_N_N2(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(N), D / N, N, N**2])


MODELS: dict[str, tuple[list[str], ModelFn]] = {
    "quadratic": (["a", "b", "c", "d", "e"], design_quadratic),
    "a+b(D/N)+c*sqrt(N)": (["a", "b_D_over_N", "c_sqrtN"], design_dn_sqrt),
    "a+b(D/N)+cN": (["a", "b_D_over_N", "c_N"], design_dn_N),
    "a+b(D/N)+c*log(N)": (["a", "b_D_over_N", "c_logN"], design_dn_log),
    "a+b(D/N)+cN+dN^2": (["a", "b_D_over_N", "c_N", "d_N2"], design_dn_N_N2),
}


def _pf(x: Any) -> float | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(x)
    except Exception:
        return None


def refresh_sheet() -> Path:
    from scripts.paper2_task1_task2_audit import correct_row, main as audit_main

    # Re-run audit export
    audit_main()
    return OUT / "corrected_sheet_succeeded.csv"


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, float]:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    n, k = X.shape
    aic = n * np.log(ss_res / n + 1e-18) + 2 * k
    return beta, r2, float(aic)


def loocv_metrics(X: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    n = len(y)
    errs = []
    preds = np.zeros(n)
    for i in range(n):
        m = np.ones(n, dtype=bool)
        m[i] = False
        beta, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
        preds[i] = float(X[i] @ beta)
        errs.append((y[i] - preds[i]) ** 2)
    rmse = float(np.sqrt(np.mean(errs)))
    ss_res = float(np.sum((y - preds) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2_loo = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return rmse, r2_loo


def pool_cells(
    rows: list[dict],
    *,
    cx: str,
    metric: str,
    min_reps: int = 3,
    max_n: int = 185,
) -> list[tuple[int, int, float, int]]:
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for r in rows:
        if r.get("ModeNorm") != "full_pipeline":
            continue
        if r.get("Complexity") != cx:
            continue
        try:
            D, N = int(r["D"]), int(r["N"])
        except Exception:
            continue
        if D not in CORE_D or N > max_n or N not in CORE_N:
            continue
        y = _pf(r.get(metric))
        if y is None or y <= 0:
            continue
        buckets[(D, N)].append(y)
    out = []
    for (D, N), vals in sorted(buckets.items()):
        if len(vals) < min_reps:
            continue
        out.append((D, N, float(np.median(vals)), len(vals)))
    return out


def evaluate_models(points: list[tuple[int, int, float, int]]) -> dict[str, Any]:
    D = np.array([p[0] for p in points], float)
    N = np.array([p[1] for p in points], float)
    y = np.array([p[2] for p in points], float)
    results = {}
    for name, (coeff_names, design) in MODELS.items():
        X = design(N, D)
        beta, r2, aic = fit(X, y)
        rmse, r2_loo = loocv_metrics(X, y)
        coeffs = {k: float(v) for k, v in zip(coeff_names, beta)}
        d_curv = coeffs.get("d")  # quadratic only
        results[name] = {
            "coeffs": coeffs,
            "r2_in_sample": r2,
            "r2_loocv": r2_loo,
            "loocv_rmse": rmse,
            "aic": aic,
            "n_params": len(coeff_names),
            "curvature_d_positive": (d_curv is not None and d_curv > 0)
            if name == "quadratic"
            else None,
        }
    # Primary: LOOCV R² (higher better); tiebreak AIC (lower better)
    ranked = sorted(
        results.items(),
        key=lambda kv: (-kv[1]["r2_loocv"], kv[1]["aic"]),
    )
    winner_name, winner = ranked[0]
    return {
        "n_cells": len(points),
        "models": results,
        "winner": winner_name,
        "winner_detail": winner,
        "ranking_by_loocv": [n for n, _ in ranked],
    }


def empirical_argmin(points: list[tuple[int, int, float, int]]) -> dict[str, Any]:
    by_d: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for D, N, y, _ in points:
        by_d[D].append((N, y))
    out = {}
    for D, pairs in sorted(by_d.items()):
        n_best, y_best = min(pairs, key=lambda t: t[1])
        out[str(D)] = {"N_emp_min": int(n_best), "T_median": float(y_best)}
    return out


def predict_time(model_name: str, coeffs: dict, N: float, D: float) -> float:
    if model_name == "quadratic":
        return (
            coeffs["a"]
            + coeffs["b"] * N
            + coeffs["c"] * D
            + coeffs["d"] * N**2
            + coeffs["e"] * N * D
        )
    if model_name == "a+b(D/N)+c*sqrt(N)":
        return coeffs["a"] + coeffs["b_D_over_N"] * (D / N) + coeffs["c_sqrtN"] * math.sqrt(N)
    if model_name == "a+b(D/N)+cN":
        return coeffs["a"] + coeffs["b_D_over_N"] * (D / N) + coeffs["c_N"] * N
    if model_name == "a+b(D/N)+c*log(N)":
        return coeffs["a"] + coeffs["b_D_over_N"] * (D / N) + coeffs["c_logN"] * math.log(N)
    if model_name == "a+b(D/N)+cN+dN^2":
        return (
            coeffs["a"]
            + coeffs["b_D_over_N"] * (D / N)
            + coeffs["c_N"] * N
            + coeffs["d_N2"] * N**2
        )
    raise ValueError(model_name)


def fit_cost_model(rows: list[dict]) -> dict[str, Any]:
    """Simple analytical: cost ≈ rate_per_node_hour * N * wall_hours, separate Spot/OD."""
    samples = []
    for r in rows:
        if r.get("ModeNorm") != "compute_only":
            continue
        if str(r.get("RealStatus", "")).upper() != "SUCCEEDED":
            continue
        try:
            N = int(float(r["N"]))
            D = int(float(r["D"]))
        except Exception:
            continue
        if N > 185:
            continue
        wall = _pf(r.get("RealWallClock")) or _pf(r.get("RealTotalPipeline"))
        cost = _pf(r.get("RealCostUSD"))
        tier = str(r.get("PricingTierNorm", "")).upper()
        if not wall or not cost or wall <= 0 or N <= 0:
            continue
        if "SPOT" in tier:
            mode = "spot"
        elif "ON" in tier:
            mode = "on_demand"
        else:
            continue
        hours = wall / 3600.0
        # implied per-node-hour rate
        rate = cost / (N * hours) if N * hours > 0 else None
        samples.append(
            {
                "mode": mode,
                "N": N,
                "D": D,
                "wall": wall,
                "cost": cost,
                "implied_rate": rate,
            }
        )

    by_mode: dict[str, list[float]] = defaultdict(list)
    for s in samples:
        if s["implied_rate"] and s["implied_rate"] > 0:
            by_mode[s["mode"]].append(s["implied_rate"])

    rates = {
        m: {
            "median_usd_per_node_hour": float(np.median(v)),
            "mean_usd_per_node_hour": float(np.mean(v)),
            "std": float(np.std(v)),
            "n": len(v),
        }
        for m, v in by_mode.items()
    }

    # Residual check vs flexible log-linear regression cost ~ a + b*log(N) + c*log(wall) + d*tier
    def rmse_simple() -> float | None:
        errs = []
        for s in samples:
            rinfo = rates.get(s["mode"])
            if not rinfo:
                continue
            pred = rinfo["median_usd_per_node_hour"] * s["N"] * (s["wall"] / 3600.0)
            errs.append((s["cost"] - pred) ** 2)
        return float(np.sqrt(np.mean(errs))) if errs else None

    # Flexible OLS on log(cost)
    flex_rmse = None
    flex_coeffs = None
    if len(samples) >= 10:
        y = np.log(np.array([s["cost"] for s in samples], float))
        N = np.array([s["N"] for s in samples], float)
        W = np.array([s["wall"] for s in samples], float)
        tier = np.array([1.0 if s["mode"] == "on_demand" else 0.0 for s in samples])
        X = np.column_stack([np.ones(len(y)), np.log(N), np.log(W), tier])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        yhat = np.exp(X @ beta)
        flex_rmse = float(np.sqrt(np.mean((np.array([s["cost"] for s in samples]) - yhat) ** 2)))
        flex_coeffs = {
            "log_cost = a + b*log(N) + c*log(wall) + d*I_ondemand": {
                "a": float(beta[0]),
                "b": float(beta[1]),
                "c": float(beta[2]),
                "d": float(beta[3]),
            }
        }

    simple_rmse = rmse_simple()
    chosen = "analytical_rate_x_N_x_hours"
    if flex_rmse is not None and simple_rmse is not None and flex_rmse < 0.7 * simple_rmse:
        chosen = "flexible_log_linear"
    note = (
        "Prefer analytical closed form when residuals are comparable; "
        "flexible wins only if RMSE < 70% of analytical."
    )
    return {
        "chosen_form": chosen,
        "form_description": "cost_usd = rate_usd_per_node_hour * N * (wall_sec/3600)",
        "rates": rates,
        "fit_quality": {
            "analytical_rmse_usd": simple_rmse,
            "flexible_rmse_usd": flex_rmse,
            "flexible_coeffs": flex_coeffs,
            "n_samples": len(samples),
        },
        "selection_note": note,
        "label": "modeled_from_compute_only_measured_costs",
    }


def config_selector(
    time_models: dict,
    cost_model: dict,
    metric_key: str = "RealWallClock",
) -> dict[str, Any]:
    rates = cost_model["rates"]
    spot_rate = rates.get("spot", {}).get("median_usd_per_node_hour")
    od_rate = rates.get("on_demand", {}).get("median_usd_per_node_hour")
    # fallback from pricing.py if missing
    if not spot_rate:
        spot_rate = 4 * 0.017 + 8 * 0.002  # vcpu+mem approx per node-hour
    if not od_rate:
        od_rate = 4 * 0.0544 + 8 * 0.0064

    table = []
    N_grid = list(CORE_N)
    weights = [0.0, 0.25, 0.5, 0.75, 1.0]

    for cx in ("low", "medium"):
        block = time_models[cx][metric_key]
        model_name = block["winner"]
        coeffs = block["winner_detail"]["coeffs"]
        for D in CORE_D:
            preds = []
            for N in N_grid:
                t = predict_time(model_name, coeffs, float(N), float(D))
                # cost Spot modeled
                c_spot = spot_rate * N * (max(t, 1.0) / 3600.0)
                c_od = od_rate * N * (max(t, 1.0) / 3600.0)
                preds.append({"N": N, "T": t, "cost_spot": c_spot, "cost_od": c_od})

            Ts = [p["T"] for p in preds]
            Cs = [p["cost_spot"] for p in preds]
            tmin, tmax = min(Ts), max(Ts)
            cmin, cmax = min(Cs), max(Cs)

            def norm(v, vmin, vmax):
                return 0.0 if vmax <= vmin else (v - vmin) / (vmax - vmin)

            n_time = min(preds, key=lambda p: p["T"])["N"]
            n_cost = min(preds, key=lambda p: p["cost_spot"])["N"]
            row = {
                "complexity": cx,
                "D": D,
                "time_model": model_name,
                "N_min_time": n_time,
                "N_min_cost_spot": n_cost,
                "T_at_N_min_time": next(p["T"] for p in preds if p["N"] == n_time),
                "cost_spot_at_N_min_cost": next(
                    p["cost_spot"] for p in preds if p["N"] == n_cost
                ),
                "weighted": {},
                "frontier": preds,
            }
            for w in weights:
                best = min(
                    preds,
                    key=lambda p: w * norm(p["T"], tmin, tmax)
                    + (1 - w) * norm(p["cost_spot"], cmin, cmax),
                )
                row["weighted"][str(w)] = {
                    "N": best["N"],
                    "T": best["T"],
                    "cost_spot_modeled": best["cost_spot"],
                    "cost_od_modeled": best["cost_od"],
                }
            table.append(row)
    return {
        "N_grid": N_grid,
        "weights": weights,
        "spot_rate_usd_per_node_hour": spot_rate,
        "od_rate_usd_per_node_hour": od_rate,
        "cost_figures_label": "modeled",
        "rows": table,
    }


def make_pareto_plots(selector: dict, out_dir: Path) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    # One PDF per complexity with 6 D panels
    for cx in ("low", "medium"):
        rows = [r for r in selector["rows"] if r["complexity"] == cx]
        fig, axes = plt.subplots(2, 3, figsize=(11, 7), constrained_layout=True)
        axes = axes.ravel()
        for i, row in enumerate(rows):
            ax = axes[i]
            frontier = row["frontier"]
            xs = [p["cost_spot"] for p in frontier]
            ys = [p["T"] for p in frontier]
            ns = [p["N"] for p in frontier]
            ax.plot(xs, ys, "o-", color="#1f4e79", markersize=5, linewidth=1.2)
            for x, y, n in zip(xs, ys, ns):
                ax.annotate(str(n), (x, y), textcoords="offset points", xytext=(3, 3), fontsize=7)
            # mark recommendations
            nt = row["N_min_time"]
            nc = row["N_min_cost_spot"]
            pt = next(p for p in frontier if p["N"] == nt)
            pc = next(p for p in frontier if p["N"] == nc)
            ax.scatter([pt["cost_spot"]], [pt["T"]], s=80, c="#c0392b", zorder=5, label="min time")
            ax.scatter(
                [pc["cost_spot"]], [pc["T"]], s=80, c="#27ae60", zorder=5, marker="s", label="min cost"
            )
            ax.set_title(f"D={row['D']:,}", fontsize=10)
            ax.set_xlabel("Modeled Spot cost (USD)")
            ax.set_ylabel("Predicted time (s)")
            ax.grid(True, alpha=0.3)
            if i == 0:
                ax.legend(fontsize=7, loc="best")
        fig.suptitle(
            f"Time–cost Pareto (N≤185) — {cx} complexity\n"
            "(costs are modeled, not billed Spot invoices)",
            fontsize=12,
        )
        path = out_dir / f"pareto_time_cost_{cx}_nle185.pdf"
        fig.savefig(path)
        plt.close(fig)
        paths.append(str(path.relative_to(REPO)))
    return paths


def illustrative_high_n_plot(rows: list[dict], out_dir: Path) -> str | None:
    """Supplementary: unreplicated N>185 — NOT used in fits."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    pts = []
    for r in rows:
        if r.get("ModeNorm") != "full_pipeline":
            continue
        try:
            N = int(r["N"])
            D = int(r["D"])
        except Exception:
            continue
        if N <= 185:
            continue
        y = _pf(r.get("RealWallClock")) or _pf(r.get("RealTotalPipeline"))
        if y:
            pts.append((r.get("Complexity"), D, N, y))
    if not pts:
        return None
    fig, ax = plt.subplots(figsize=(8, 5))
    for cx, color in (("low", "#1f4e79"), ("medium", "#c0392b")):
        sub = [p for p in pts if p[0] == cx]
        if not sub:
            continue
        ax.scatter(
            [p[2] for p in sub],
            [p[3] for p in sub],
            c=color,
            alpha=0.7,
            label=f"{cx} (n={len(sub)} single-run cells)",
        )
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("Wall / Total Pipeline (s)")
    ax.set_title(
        "UNREPLICATED N>185 full_pipeline rows — illustrative only\n"
        "NOT used in any fitted model"
    )
    ax.legend()
    ax.grid(True, alpha=0.3)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "supplementary_unreplicated_N_gt185.pdf"
    fig.savefig(path)
    plt.close(fig)
    return str(path.relative_to(REPO))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-sheet", action="store_true")
    ap.add_argument("--min-reps", type=int, default=3)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    csv_path = OUT / "corrected_sheet_succeeded.csv"
    if args.refresh_sheet or not csv_path.is_file():
        print("Refreshing sheet export…")
        # inline refresh without re-entering audit CLI noise too much
        from descriptor_cloud_benchmark.monitoring.sheets import read_results_rows
        from scripts.paper2_task1_task2_audit import correct_row

        sid = os.environ.get("GOOGLE_SHEETS_ID")
        raw = read_results_rows(sid, limit=50000)
        headers = raw[0]
        corrected = []
        for row in raw[1:]:
            while len(row) < len(headers):
                row.append("")
            corrected.append(correct_row({headers[i]: row[i] for i in range(len(headers))}))
        # minimal succeed write
        out_cols = [
            "Timestamp",
            "ExperimentID",
            "ModeNorm",
            "D",
            "N",
            "Complexity",
            "schema",
            "is_shifted",
            "RealStatus",
            "RealJobID",
            "RealClusterParallel",
            "RealWallClock",
            "RealTotalPipeline",
            "RealComputation",
            "PricingTierNorm",
            "RealCostUSD",
            "RealCostSpotEquiv",
            "RealCostOnDemandEquiv",
            "CostSpotEquivModeledUSD",
            "CostSpotEquivModeledMethod",
        ]
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
            w.writeheader()
            for r in corrected:
                if r.get("RealStatus") != "SUCCEEDED":
                    continue
                w.writerow({k: r.get(k, "") for k in out_cols})
        print(f"Wrote {csv_path}")

    rows = load_rows(csv_path)

    # Verify replicate coverage
    coverage = {}
    under = []
    for cx in ("low", "medium"):
        for metric in ("RealWallClock", "RealTotalPipeline"):
            pts = pool_cells(rows, cx=cx, metric=metric, min_reps=1, max_n=185)
            # recount
            buckets = defaultdict(int)
            for r in rows:
                if r.get("ModeNorm") != "full_pipeline" or r.get("Complexity") != cx:
                    continue
                try:
                    D, N = int(r["D"]), int(r["N"])
                except Exception:
                    continue
                if D in CORE_D and N in CORE_N:
                    buckets[(D, N)] += 1
            ge3 = sum(1 for v in buckets.values() if v >= args.min_reps)
            coverage[f"{cx}"] = {
                "cells_present": len(buckets),
                "cells_ge3": ge3,
                "expected": len(CORE_D) * len(CORE_N),
                "hist": dict(
                    __import__("collections").Counter(buckets.values())
                ),
            }
            for (D, N), v in buckets.items():
                if v < args.min_reps:
                    under.append({"cx": cx, "D": D, "N": N, "have": v})

    if under:
        print(f"WARNING: {len(under)} cells still <{args.min_reps} reps — excluded from fits")
        (OUT / "task3_under_replicated_cells.json").write_text(json.dumps(under, indent=2))

    # Prefer RealWallClock; also fit TotalPipeline as sensitivity
    time_results: dict[str, Any] = {}
    for cx in ("low", "medium"):
        time_results[cx] = {}
        for metric in ("RealWallClock", "RealTotalPipeline"):
            pts = pool_cells(rows, cx=cx, metric=metric, min_reps=args.min_reps, max_n=185)
            if len(pts) < 10:
                time_results[cx][metric] = {"error": "too_few_cells", "n": len(pts)}
                continue
            ev = evaluate_models(pts)
            ev["empirical_argmin_N_per_D"] = empirical_argmin(pts)
            # N* from quadratic if d>0
            q = ev["models"]["quadratic"]
            nstars = {}
            if q["curvature_d_positive"]:
                b, d, e = q["coeffs"]["b"], q["coeffs"]["d"], q["coeffs"]["e"]
                for Dv in CORE_D:
                    raw = -(b + e * Dv) / (2 * d)
                    nstars[str(Dv)] = {
                        "raw": round(raw, 2),
                        "clamped": int(np.clip(round(raw), 25, 185)),
                    }
            else:
                nstars = {"note": "d<=0 — no interior minimum from quadratic"}
            ev["quadratic_analytic_Nstar"] = nstars
            # flag medium reversal
            emp = ev["empirical_argmin_N_per_D"]
            n5 = emp.get("5000", {}).get("N_emp_min")
            n50 = emp.get("50000", {}).get("N_emp_min")
            ev["nstar_reversal_flag"] = {
                "N_at_D5000": n5,
                "N_at_D50000": n50,
                "reversal_persists": bool(n5 and n50 and n50 < n5),
                "delta": (n50 - n5) if (n5 and n50) else None,
            }
            time_results[cx][metric] = ev

    (OUT / "task3_time_models_nle185.json").write_text(json.dumps(time_results, indent=2))

    cost_model = fit_cost_model(rows)
    (OUT / "task4_cost_model.json").write_text(json.dumps(cost_model, indent=2))

    # Selector uses WallClock winners when available
    selector = config_selector(time_results, cost_model, "RealWallClock")
    # also dump callable helper module path note
    (OUT / "task5_config_selector_table.json").write_text(json.dumps(selector, indent=2))

    # Write a small Python callable
    callable_path = OUT / "config_selector.py"
    callable_path.write_text(
        '''"""Callable config selector loaded from task5_config_selector_table.json."""
from __future__ import annotations
import json
from pathlib import Path

_TABLE = json.loads((Path(__file__).parent / "task5_config_selector_table.json").read_text())

def recommend(D: int, complexity: str, w: float = 0.5, provisioning: str = "spot") -> dict:
    """Return recommended N for given D, complexity, weight w in [0,1] (1=time-only)."""
    complexity = complexity.lower()
    key = str(float(w)) if str(w) in ("0.0","0.25","0.5","0.75","1.0") else None
    # normalize
    wmap = {0: "0.0", 0.25: "0.25", 0.5: "0.5", 0.75: "0.75", 1: "1.0", 1.0: "1.0"}
    wk = wmap.get(w, str(w))
    for row in _TABLE["rows"]:
        if row["D"] == int(D) and row["complexity"] == complexity:
            if wk in row["weighted"]:
                rec = dict(row["weighted"][wk])
                rec["provisioning"] = provisioning
                rec["cost_label"] = "modeled"
                rec["D"] = D
                rec["complexity"] = complexity
                rec["w"] = w
                return rec
            raise KeyError(f"weight {w} not in table")
    raise KeyError(f"No row for D={D} complexity={complexity}")
'''
    )

    fig_paths = make_pareto_plots(selector, FIGS)
    supp = illustrative_high_n_plot(rows, FIGS)

    # One-page summary
    summary_lines = []
    summary_lines.append("# Paper 2 — Tasks 3–5 summary (N≤185 only)\n")
    summary_lines.append(f"Generated: `{datetime.now(timezone.utc).isoformat()}`\n\n")
    summary_lines.append("## Scope\n")
    summary_lines.append("- Fitted on full_pipeline cells with N≤185, D∈{5…50}k, ≥3 reps.\n")
    summary_lines.append("- N>185 excluded from all fits (supplementary plot only).\n")
    summary_lines.append(f"- Coverage: `{json.dumps(coverage)}`\n")
    summary_lines.append(f"- Under-replicated excluded: {len(under)} cells\n\n")
    summary_lines.append("## Task 3 — time models\n")
    for cx in ("low", "medium"):
        block = time_results[cx].get("RealWallClock", {})
        if "error" in block:
            summary_lines.append(f"- {cx} WallClock: ERROR {block}\n")
            continue
        summary_lines.append(
            f"- **{cx}** winner=`{block['winner']}` "
            f"R²={block['winner_detail']['r2_in_sample']:.3f} "
            f"LOOCV-R²={block['winner_detail']['r2_loocv']:.3f} "
            f"AIC={block['winner_detail']['aic']:.1f} "
            f"quad_d>0={block['models']['quadratic']['curvature_d_positive']}\n"
        )
        summary_lines.append(f"  emp argmin: `{block['empirical_argmin_N_per_D']}`\n")
        summary_lines.append(f"  reversal flag: `{block['nstar_reversal_flag']}`\n")
    summary_lines.append("\n## Task 4 — cost model\n")
    summary_lines.append(f"- Chosen: **{cost_model['chosen_form']}** ({cost_model['form_description']})\n")
    summary_lines.append(f"- Rates: `{cost_model['rates']}`\n")
    summary_lines.append(f"- RMSE analytical vs flexible: `{cost_model['fit_quality']}`\n")
    summary_lines.append("\n## Task 5 — headline recommendations (w=0.5, Spot modeled)\n")
    for row in selector["rows"]:
        rec = row["weighted"]["0.5"]
        summary_lines.append(
            f"- {row['complexity']} D={row['D']}: N*={rec['N']} "
            f"T≈{rec['T']:.1f}s cost_spot_modeled≈${rec['cost_spot_modeled']:.4f} "
            f"(minT N={row['N_min_time']}, minCost N={row['N_min_cost_spot']})\n"
        )
    summary_lines.append("\n## Figures\n")
    for p in fig_paths:
        summary_lines.append(f"- `{p}`\n")
    if supp:
        summary_lines.append(f"- `{supp}` (unreplicated N>185 — not fitted)\n")
    summary_lines.append("\n## Files\n")
    summary_lines.append("- `tmp/paper2_rebuild/task3_time_models_nle185.json`\n")
    summary_lines.append("- `tmp/paper2_rebuild/task4_cost_model.json`\n")
    summary_lines.append("- `tmp/paper2_rebuild/task5_config_selector_table.json`\n")
    summary_lines.append("- `tmp/paper2_rebuild/config_selector.py`\n")

    (OUT / "TASKS3_5_SUMMARY.md").write_text("".join(summary_lines))
    print("".join(summary_lines))


if __name__ == "__main__":
    main()
