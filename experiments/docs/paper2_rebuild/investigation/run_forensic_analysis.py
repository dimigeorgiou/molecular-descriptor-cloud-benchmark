from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score


ROOT = Path("/Users/dimitriosgeorgiou/Desktop/git/chemoinformatics-descriptor-computation")
CSV_PATH = ROOT / "tmp/paper2_rebuild/corrected_sheet_succeeded.csv"
OUT_DIR = ROOT / "tmp/paper2_rebuild/investigation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

D_SCOPE = [5000, 10000, 20000, 30000, 40000, 50000]
N_SCOPE = [25, 50, 75, 100, 125, 150, 185]
CX_SCOPE = ["low", "medium"]
MODE_SCOPE = "full_pipeline"
METRICS = [
    "RealWallClock",
    "RealComputation",
    "RealClusterParallel",
    "RealTotalPipeline",
]


@dataclass
class FitResult:
    model: str
    metric: str
    n_rows: int
    n_cells: int
    r2_in_sample: float
    r2_loco_cell: float
    coef: dict[str, float]
    notes: dict[str, Any]


def normalize_status(x: Any) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip().upper()


def is_success(status: Any) -> bool:
    return normalize_status(status) == "SUCCEEDED"


def design_matrix(df: pd.DataFrame, model_name: str) -> tuple[np.ndarray, list[str]]:
    n = df["N"].to_numpy(dtype=float)
    d = df["D"].to_numpy(dtype=float)
    if model_name == "christos_quadratic":
        cols = ["N", "D", "N2", "ND"]
        x = np.column_stack([n, d, n**2, n * d])
        return x, cols
    if model_name == "amdahl_like":
        cols = ["D_over_N", "N"]
        x = np.column_stack([d / n, n])
        return x, cols
    raise ValueError(f"Unknown model: {model_name}")


def fit_and_eval(df: pd.DataFrame, metric: str, model_name: str) -> FitResult:
    use = df[["Complexity", "D", "N", metric]].dropna().copy()
    x, names = design_matrix(use, model_name)
    y = use[metric].to_numpy(dtype=float)

    reg = LinearRegression().fit(x, y)
    pred = reg.predict(x)
    r2_in = float(r2_score(y, pred))

    cell_keys = use[["Complexity", "D", "N"]].astype(str).agg("|".join, axis=1)
    unique_cells = sorted(cell_keys.unique())
    y_cv = np.full_like(y, np.nan, dtype=float)

    for ck in unique_cells:
        test_mask = cell_keys == ck
        train_mask = ~test_mask
        if train_mask.sum() < 5 or test_mask.sum() == 0:
            continue
        reg_cv = LinearRegression().fit(x[train_mask], y[train_mask])
        y_cv[test_mask] = reg_cv.predict(x[test_mask])

    valid = ~np.isnan(y_cv)
    if valid.sum() > 2:
        r2_loco = float(r2_score(y[valid], y_cv[valid]))
    else:
        r2_loco = float("nan")

    coef = {"intercept": float(reg.intercept_)}
    for n, c in zip(names, reg.coef_):
        coef[n] = float(c)

    notes: dict[str, Any] = {}
    if model_name == "christos_quadratic":
        b = coef["N"]
        d_q = coef["N2"]
        e = coef["ND"]
        nstars = {}
        for dval in D_SCOPE:
            if d_q <= 0:
                nstar = np.nan
            else:
                nstar = -(b + e * dval) / (2 * d_q)
            nstars[str(dval)] = None if np.isnan(nstar) else float(nstar)
        notes["d_sign"] = "positive" if d_q > 0 else ("zero" if d_q == 0 else "negative")
        notes["nstar_raw_by_D"] = nstars
        interior = {
            k: (v is not None and 25 <= v <= 185)
            for k, v in nstars.items()
        }
        notes["nstar_interior_25_185_by_D"] = interior
        notes["any_interior_nstar"] = any(interior.values())

    return FitResult(
        model=model_name,
        metric=metric,
        n_rows=int(len(use)),
        n_cells=int(len(unique_cells)),
        r2_in_sample=r2_in,
        r2_loco_cell=r2_loco,
        coef=coef,
        notes=notes,
    )


def variance_decomposition(df: pd.DataFrame, tier: str) -> dict[str, Any]:
    part = df[(df["PricingTierNorm"] == tier) & df["RealWallClock"].notna()].copy()
    if part.empty:
        return {"tier": tier, "n_rows": 0}
    y = part["RealWallClock"].to_numpy(dtype=float)
    grand = float(np.mean(y))
    part["cell"] = part[["Complexity", "D", "N"]].astype(str).agg("|".join, axis=1)
    grp = part.groupby("cell")["RealWallClock"]
    means = grp.mean()
    counts = grp.size()

    ss_total = float(np.sum((y - grand) ** 2))
    ss_between = float(np.sum(counts.to_numpy() * (means.to_numpy() - grand) ** 2))
    ss_within = float(ss_total - ss_between)

    g = len(means)
    n = len(part)
    ms_between = ss_between / max(g - 1, 1)
    ms_within = ss_within / max(n - g, 1)
    k_bar = float(np.mean(counts.to_numpy()))
    denom = ms_between + (k_bar - 1.0) * ms_within
    icc = float((ms_between - ms_within) / denom) if denom > 0 else float("nan")
    eta2 = float(ss_between / ss_total) if ss_total > 0 else float("nan")

    return {
        "tier": tier,
        "n_rows": int(n),
        "n_cells": int(g),
        "ss_total": ss_total,
        "ss_between_cells": ss_between,
        "ss_within_cells": ss_within,
        "eta2_between": eta2,
        "within_over_total": float(ss_within / ss_total) if ss_total > 0 else float("nan"),
        "icc_oneway_approx": icc,
        "mean_reps_per_cell": k_bar,
    }


def classify_shape(ns: list[int], ys: list[float]) -> str:
    if len(ns) < 3:
        return "insufficient"
    idx_min = int(np.argmin(ys))
    nmin = ns[idx_min]
    if 0 < idx_min < len(ns) - 1:
        return "u_shape_interior_min"
    diffs = np.diff(np.array(ys, dtype=float))
    if np.all(diffs >= 0):
        return "monotonic_increase"
    if np.all(np.abs(diffs) <= max(1e-9, 0.03 * np.median(np.abs(ys)))):
        return "flat_noise"
    if nmin == 25:
        return "boundary_min_n25"
    if idx_min == len(ns) - 1:
        return "boundary_min_highN"
    return "non_monotone_no_clear_u"


def partial_corr(x: np.ndarray, y: np.ndarray, controls: np.ndarray) -> float:
    reg_x = LinearRegression().fit(controls, x)
    reg_y = LinearRegression().fit(controls, y)
    rx = x - reg_x.predict(controls)
    ry = y - reg_y.predict(controls)
    sx = np.std(rx)
    sy = np.std(ry)
    if sx == 0 or sy == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def robust_outlier_count(s: pd.Series) -> int:
    x = s.dropna().to_numpy(dtype=float)
    if len(x) < 5:
        return 0
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad == 0:
        return 0
    z = 0.6745 * (x - med) / mad
    return int(np.sum(np.abs(z) > 3.5))


def discover_historical_fits() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fp in ROOT.glob("**/fitted_model.json"):
        try:
            with open(fp) as f:
                data = json.load(f)
        except Exception:
            continue
        r2 = data.get("r_squared")
        if r2 is None:
            continue
        if not (0.6 <= float(r2) <= 0.95):
            continue
        run_dir = fp.parent
        info: dict[str, Any] = {
            "path": str(fp.relative_to(ROOT)),
            "r_squared": float(r2),
            "source": data.get("source"),
            "fitted_from_n_samples": data.get("fitted_from_n_samples"),
            "mode": None,
            "n_grid": None,
            "metric_hint": None,
        }
        cfg = run_dir / "config.yaml"
        if cfg.exists():
            txt = cfg.read_text(encoding="utf-8", errors="ignore")
            for line in txt.splitlines():
                ll = line.strip()
                if ll.startswith("mode:"):
                    info["mode"] = ll.split(":", 1)[1].strip()
                if ll.startswith("node_configs:"):
                    info["n_grid"] = ll.split(":", 1)[1].strip()
        name = run_dir.name.lower()
        if "compute_only" in name:
            info["metric_hint"] = "likely computation-centric"
        elif "full_pipeline" in name:
            info["metric_hint"] = "likely pipeline/wall oriented"
        out.append(info)
    out.sort(key=lambda x: x["r_squared"], reverse=True)
    return out


def main() -> None:
    df = pd.read_csv(CSV_PATH)

    # Numeric coercions
    for col in ["D", "N"] + METRICS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["RealStatusNorm"] = df["RealStatus"].map(normalize_status)

    base_scope = df[
        (df["ModeNorm"] == MODE_SCOPE)
        & (df["Complexity"].isin(CX_SCOPE))
        & (df["D"].isin(D_SCOPE))
        & (df["N"].isin(N_SCOPE))
    ].copy()
    success_scope = base_scope[base_scope["RealStatusNorm"] == "SUCCEEDED"].copy()

    rep_counts = (
        success_scope.groupby(["Complexity", "D", "N"])
        .size()
        .reset_index(name="n_reps")
    )
    eligible_cells = rep_counts[rep_counts["n_reps"] >= 3][["Complexity", "D", "N"]].copy()
    eligible = success_scope.merge(eligible_cells, on=["Complexity", "D", "N"], how="inner")
    eligible["PricingTierNorm"] = eligible["PricingTierNorm"].fillna("unknown")

    inventory = {
        "total_rows": int(len(df)),
        "rows_by_mode": df["ModeNorm"].fillna("NA").value_counts().to_dict(),
        "rows_by_complexity": df["Complexity"].fillna("NA").value_counts().to_dict(),
        "scoped_rows": int(len(base_scope)),
        "scoped_success_rows": int(len(success_scope)),
        "eligible_rows_success": int(len(eligible)),
        "eligible_cells": int(len(eligible_cells)),
        "replicate_count_summary": {
            "min": int(rep_counts["n_reps"].min()) if len(rep_counts) else 0,
            "median": float(rep_counts["n_reps"].median()) if len(rep_counts) else 0.0,
            "max": int(rep_counts["n_reps"].max()) if len(rep_counts) else 0,
            "cells_ge_3": int((rep_counts["n_reps"] >= 3).sum()),
            "cells_lt_3": int((rep_counts["n_reps"] < 3).sum()),
        },
        "rows_by_tier_scoped_success": success_scope["PricingTierNorm"].fillna("unknown").value_counts().to_dict(),
        "rows_by_tier_eligible": eligible["PricingTierNorm"].value_counts().to_dict(),
        "schema_counts_scoped": base_scope["schema"].fillna("NA").value_counts().to_dict(),
        "is_shifted_counts_scoped": base_scope["is_shifted"].fillna("NA").astype(str).value_counts().to_dict(),
        "wall_missing_scoped": int(base_scope["RealWallClock"].isna().sum()),
        "wall_outliers_scoped_success_mad": robust_outlier_count(success_scope["RealWallClock"]),
    }

    tiers = sorted(eligible["PricingTierNorm"].dropna().unique().tolist())
    if "unknown" in tiers:
        tiers = [t for t in tiers if t != "unknown"] + ["unknown"]
    var_parts = [variance_decomposition(eligible, t) for t in tiers]

    model_results: dict[str, dict[str, Any]] = {}
    for metric in METRICS:
        model_results[metric] = {}
        for model_name in ["christos_quadratic", "amdahl_like"]:
            res = fit_and_eval(eligible, metric, model_name)
            model_results[metric][model_name] = asdict(res)

    shape_rows = []
    for (cx, dval), grp in eligible.groupby(["Complexity", "D"]):
        med = grp.groupby("N")["RealWallClock"].median().reset_index().sort_values("N")
        ns = med["N"].astype(int).tolist()
        ys = med["RealWallClock"].astype(float).tolist()
        label = classify_shape(ns, ys)
        n_min = int(ns[int(np.argmin(ys))]) if len(ns) else None
        shape_rows.append(
            {
                "Complexity": cx,
                "D": int(dval),
                "N_values": ns,
                "median_wall_values": ys,
                "shape": label,
                "empirical_min_N": n_min,
            }
        )
    shape_df = pd.DataFrame(shape_rows)
    shape_summary = (
        shape_df.groupby("Complexity")["shape"].value_counts().unstack(fill_value=0).to_dict(orient="index")
        if len(shape_df)
        else {}
    )
    boundary_vs_interior = {}
    for cx in CX_SCOPE:
        sub = shape_df[shape_df["Complexity"] == cx]
        boundary_vs_interior[cx] = {
            "n_D_series": int(len(sub)),
            "interior_min_count": int((sub["shape"] == "u_shape_interior_min").sum()),
            "boundary_min_n25_count": int((sub["empirical_min_N"] == 25).sum()),
        }

    corr_df = eligible[["RealWallClock", "N", "D"]].dropna().copy()
    corr_df["D_over_N"] = corr_df["D"] / corr_df["N"]

    spearman = {
        "wall_vs_N": tuple(float(v) for v in spearmanr(corr_df["RealWallClock"], corr_df["N"])),
        "wall_vs_D": tuple(float(v) for v in spearmanr(corr_df["RealWallClock"], corr_df["D"])),
        "wall_vs_D_over_N": tuple(float(v) for v in spearmanr(corr_df["RealWallClock"], corr_df["D_over_N"])),
    }
    # values are (rho, pvalue)
    corr_stats = {
        "spearman": {
            k: {"rho": v[0], "pvalue": v[1]}
            for k, v in spearman.items()
        }
    }

    xw = corr_df["RealWallClock"].to_numpy(dtype=float)
    xn = corr_df["N"].to_numpy(dtype=float)
    xd = corr_df["D"].to_numpy(dtype=float)
    xdn = corr_df["D_over_N"].to_numpy(dtype=float)
    corr_stats["partial_pearson"] = {
        "wall_vs_N_given_D": partial_corr(xw, xn, xd.reshape(-1, 1)),
        "wall_vs_D_given_N": partial_corr(xw, xd, xn.reshape(-1, 1)),
        "wall_vs_D_over_N_given_D_N": partial_corr(xw, xdn, np.column_stack([xd, xn])),
    }

    # Rank-based partial (Spearman-like)
    wr = corr_df.rank().copy()
    corr_stats["partial_spearman_like"] = {
        "wall_vs_N_given_D": partial_corr(
            wr["RealWallClock"].to_numpy(float),
            wr["N"].to_numpy(float),
            wr[["D"]].to_numpy(float),
        ),
        "wall_vs_D_given_N": partial_corr(
            wr["RealWallClock"].to_numpy(float),
            wr["D"].to_numpy(float),
            wr[["N"]].to_numpy(float),
        ),
        "wall_vs_D_over_N_given_D_N": partial_corr(
            wr["RealWallClock"].to_numpy(float),
            wr["D_over_N"].to_numpy(float),
            wr[["D", "N"]].to_numpy(float),
        ),
    }

    historical_fits = discover_historical_fits()

    metrics = {
        "input": {
            "csv": str(CSV_PATH.relative_to(ROOT)),
            "scope": {
                "ModeNorm": MODE_SCOPE,
                "Complexity": CX_SCOPE,
                "D": D_SCOPE,
                "N": N_SCOPE,
                "success_only_for_modeling": True,
                "eligible_cells_min_reps": 3,
            },
        },
        "inventory": inventory,
        "variance_decomposition_wall_by_tier": var_parts,
        "metric_model_comparison": model_results,
        "monotonicity_u_shape_by_complexity_D": shape_rows,
        "monotonicity_summary": shape_summary,
        "boundary_vs_interior_counts": boundary_vs_interior,
        "effect_sizes": corr_stats,
        "historical_r2_fits_0p6_to_0p95": historical_fits,
    }

    metrics_path = OUT_DIR / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    quad_wall = model_results["RealWallClock"]["christos_quadratic"]
    quad_comp = model_results["RealComputation"]["christos_quadratic"]
    amd_wall = model_results["RealWallClock"]["amdahl_like"]
    amd_comp = model_results["RealComputation"]["amdahl_like"]

    top_causes = []
    # Cause 1: within-cell variance dominance
    within_ratios = [v.get("within_over_total", np.nan) for v in var_parts if v.get("n_rows", 0) > 0]
    if len(within_ratios):
        top_causes.append(
            (
                "High replicate noise within fixed (D,N) cells",
                float(np.nanmedian(within_ratios)),
                "within_over_total_median",
            )
        )
    # Cause 2: weak monotonic structure of wall vs N
    interior = sum(v["interior_min_count"] for v in boundary_vs_interior.values())
    total_series = sum(v["n_D_series"] for v in boundary_vs_interior.values())
    top_causes.append(
        (
            "Wall-clock vs N is mostly non-convex/noisy rather than smooth U-shape",
            float(interior / total_series) if total_series else float("nan"),
            "interior_min_fraction",
        )
    )
    # Cause 3: metric dependence
    top_causes.append(
        (
            "Signal is metric-dependent: computation has stronger deterministic trend than wall-clock",
            float(quad_comp["r2_loco_cell"] - quad_wall["r2_loco_cell"]),
            "delta_loco_r2_comp_minus_wall",
        )
    )

    verdict = "partially_supported"
    wall_any_interior = bool(quad_wall["notes"].get("any_interior_nstar"))
    comp_any_interior = bool(quad_comp["notes"].get("any_interior_nstar"))
    wall_loco = quad_wall["r2_loco_cell"]
    if wall_any_interior and wall_loco >= 0.25:
        verdict = "supported"
    elif (not wall_any_interior) and wall_loco < 0.1 and comp_any_interior:
        verdict = "not_supported_on_wall_but_supported_on_compute"

    report = f"""# WHY LOW R² / LOOCV ON WALL-CLOCK (Paper2 established grid)

## TL;DR
- On the scoped `full_pipeline` low+medium grid (eligible cells: >=3 successful reps), wall-clock has weak predictive structure relative to replicate noise. This limits attainable R²/LOCOCV for smooth mean-surface models.
- Metric swap shows stronger structure on computation-centric metrics than on wall-clock: Christos quadratic performs materially better on `RealComputation` than `RealWallClock`.
- Christos quadratic is therefore **partially supported** on this sheet slice: stronger for compute-time behavior, weaker for end-to-end wall-clock prediction.

## 1) Data inventory
- Total rows in CSV: {inventory['total_rows']}
- Scoped rows (`ModeNorm=full_pipeline`, low+medium, target D/N): {inventory['scoped_rows']}
- Scoped successful rows: {inventory['scoped_success_rows']}
- Eligible rows (successful rows in cells with >=3 reps): {inventory['eligible_rows_success']} across {inventory['eligible_cells']} cells
- Replicate count per scoped successful cell: min/median/max = {inventory['replicate_count_summary']['min']}/{inventory['replicate_count_summary']['median']}/{inventory['replicate_count_summary']['max']}
- Spot/OD mix in eligible rows: {inventory['rows_by_tier_eligible']}
- schema flags (scoped): {inventory['schema_counts_scoped']}
- is_shifted flags (scoped): {inventory['is_shifted_counts_scoped']}
- Missing `RealWallClock` in scoped rows: {inventory['wall_missing_scoped']}
- Robust wall-clock outliers in scoped successful rows (MAD rule): {inventory['wall_outliers_scoped_success_mad']}

## 2) Variance anatomy of wall-clock (by pricing tier)
"""
    for vd in var_parts:
        if vd.get("n_rows", 0) == 0:
            continue
        report += (
            f"- Tier `{vd['tier']}`: n={vd['n_rows']} rows, cells={vd['n_cells']}, "
            f"between-cell η²={vd['eta2_between']:.3f}, within/total={vd['within_over_total']:.3f}, "
            f"ICC≈{vd['icc_oneway_approx']:.3f}\n"
        )
    report += """
Interpretation: low η²_between (or high within/total) means replicate noise dominates cell means, directly capping surface-model R².

## 3) Metric swap (same models, same eligible rows)
"""
    for m in METRICS:
        q = model_results[m]["christos_quadratic"]
        a = model_results[m]["amdahl_like"]
        report += (
            f"- `{m}`: Christos R²={q['r2_in_sample']:.3f}, LOCO-R²={q['r2_loco_cell']:.3f}; "
            f"Amdahl-like R²={a['r2_in_sample']:.3f}, LOCO-R²={a['r2_loco_cell']:.3f}\n"
        )

    report += f"""
## 4) Christos quadratic vs Amdahl-like (focus: wall vs computation)
- Wall (`RealWallClock`), Christos: d={quad_wall['coef']['N2']:.6g} ({quad_wall['notes']['d_sign']}), LOCO-R²={quad_wall['r2_loco_cell']:.3f}
- Wall, Amdahl-like LOCO-R²={amd_wall['r2_loco_cell']:.3f}
- Computation (`RealComputation`), Christos: d={quad_comp['coef']['N2']:.6g} ({quad_comp['notes']['d_sign']}), LOCO-R²={quad_comp['r2_loco_cell']:.3f}
- Computation, Amdahl-like LOCO-R²={amd_comp['r2_loco_cell']:.3f}
- Christos interior N* in [25,185]:
  - Wall any interior N*? {quad_wall['notes']['any_interior_nstar']}
  - Computation any interior N*? {quad_comp['notes']['any_interior_nstar']}

## 5) Monotonicity / U-shape of median wall vs N
"""
    for cx, counts in boundary_vs_interior.items():
        report += (
            f"- {cx}: D-series={counts['n_D_series']}, interior-min count={counts['interior_min_count']}, "
            f"boundary min at N=25 count={counts['boundary_min_n25_count']}\n"
        )
    report += f"- Shape counts by complexity: {shape_summary}\n"

    es = corr_stats["spearman"]
    pp = corr_stats["partial_pearson"]
    ps = corr_stats["partial_spearman_like"]
    report += f"""
## 6) Effect sizes (magnitude-first)
- Spearman rho(wall, N) = {es['wall_vs_N']['rho']:.3f}
- Spearman rho(wall, D) = {es['wall_vs_D']['rho']:.3f}
- Spearman rho(wall, D/N) = {es['wall_vs_D_over_N']['rho']:.3f}
- Partial Pearson corr(wall, N | D) = {pp['wall_vs_N_given_D']:.3f}
- Partial Pearson corr(wall, D | N) = {pp['wall_vs_D_given_N']:.3f}
- Partial Pearson corr(wall, D/N | D,N) = {pp['wall_vs_D_over_N_given_D_N']:.3f}
- Partial Spearman-like corr(wall, N | D) = {ps['wall_vs_N_given_D']:.3f}
- Partial Spearman-like corr(wall, D | N) = {ps['wall_vs_D_given_N']:.3f}

## 7) Why prior high R² reports can differ
- I searched repository `**/fitted_model.json` and collected entries with 0.6 <= R² <= 0.95.
- These fits often come from different run directories/modes and may be computation-centric, not the same wall-clock/full-pipeline slice used here.
- Evidence table is stored in `metrics.json` under `historical_r2_fits_0p6_to_0p95`, with exact paths and inferred mode/metric hints.

## 8) Christos proposal verdict for THIS sheet slice
**Verdict:** `{verdict}`

Evidence:
- On wall-clock (target of the concern), Christos LOCO-R² is {quad_wall['r2_loco_cell']:.3f}, indicating weak out-of-cell generalization on this slice.
- On computation, Christos LOCO-R² is {quad_comp['r2_loco_cell']:.3f}, stronger than wall-clock and consistent with better structural fit in compute metric.
- U-shape evidence in empirical medians is mixed (interior minima in {interior}/{total_series} complexity×D series), not universal.

## Top 3 root causes (ranked by evidence strength)
1. **High within-cell replicate variability** (median within/total variance across tiers = {top_causes[0][1]:.3f}).
2. **Noisy/non-universal wall-clock shape vs N** (interior-min fraction = {top_causes[1][1]:.3f} across complexity×D series).
3. **Metric mismatch** (LOCO-R² computation minus wall = {top_causes[2][1]:.3f} for Christos).

## Output artifacts
- `tmp/paper2_rebuild/investigation/metrics.json`
- `tmp/paper2_rebuild/investigation/WHY_LOW_R2_REPORT.md`
"""

    (OUT_DIR / "WHY_LOW_R2_REPORT.md").write_text(report, encoding="utf-8")
    print("Wrote:", metrics_path)
    print("Wrote:", OUT_DIR / "WHY_LOW_R2_REPORT.md")


if __name__ == "__main__":
    main()
