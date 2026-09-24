#!/usr/bin/env python3
"""
Paper handoff audit against current Google Sheets Results.

Answers:
1) Reproduce Table 1 (R²≈0.851) and Table 3 (R²≈0.442/0.675)
2) LOOCV: quadratic T(N,D)=a+bN+cD+dN²+eND vs Amdahl-like a+b(D/N)+cN
3) Extend N grid beyond 128 when data exists
4) Warm-keeper cutoff refits
5) D=30000 presence / exclusion
6) True replicate counts + full-replicate (row-level) refit

Usage:
  PYTHONPATH=. python scripts/paper_audit_handoff.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT = REPO / "tmp/paper_audit"
WARM_KEEPER_UTC = datetime(2026, 7, 10, 0, 29, 37, tzinfo=timezone.utc)

# Paper Table 3 design
TABLE3_D = {5000, 10000, 20000, 40000, 50000}
TABLE3_N = {2, 4, 8, 16, 32, 64, 128}
PAPER_TABLE3 = {
    "low": {
        "a": 39.862,
        "b": -0.114,
        "c": 0.00225,
        "d": 0.00581,
        "e": -1.09e-5,
        "r2": 0.442,
        "n": 35,
    },
    "medium": {
        "a": 59.975,
        "b": -1.047,
        "c": 0.00336,
        "d": 0.00922,
        "e": -3.39e-6,
        "r2": 0.675,
        "n": 35,
    },
}


def _parse_ts(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _replica(notes: str) -> int:
    if "replica=" in notes:
        try:
            return int(notes.split("replica=")[1].split("/")[0].split(";")[0].strip())
        except Exception:
            return 1
    return 1


def _f(row: list[str], idx: dict[str, int], name: str, default: float | None = None) -> float | None:
    i = idx.get(name)
    if i is None or i >= len(row) or row[i] == "":
        return default
    try:
        return float(row[i])
    except Exception:
        return default


def _design_quadratic(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(N), N, D, N**2, N * D])


def _design_dn(N: np.ndarray, D: np.ndarray) -> np.ndarray:
    # T = a + b(D/N) + cN
    return np.column_stack([np.ones_like(N), D / N, N])


def _fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, float]:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    n, k = X.shape
    aic = n * np.log(ss_res / n + 1e-18) + 2 * k
    return beta, r2, float(aic)


def _loocv_rmse(X: np.ndarray, y: np.ndarray) -> float:
    n = len(y)
    errs = []
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        beta, *_ = np.linalg.lstsq(X[mask], y[mask], rcond=None)
        pred = float(X[i] @ beta)
        errs.append((y[i] - pred) ** 2)
    return float(np.sqrt(np.mean(errs)))


def _nstar_quad(b: float, d: float, e: float, D: float) -> float | None:
    if d <= 0:
        return None
    return -(b + e * D) / (2 * d)


def _load_rows() -> tuple[list[list[str]], dict[str, int]]:
    load_dotenv(REPO / ".env")
    from src.monitoring.sheets import read_results_rows

    sid = os.environ.get("GOOGLE_SHEETS_ID") or "1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs"
    rows = read_results_rows(sid, limit=50000)
    idx = {h: i for i, h in enumerate(rows[0])}
    return rows, idx


def _is_spot(row: list[str], idx: dict[str, int]) -> bool:
    tier = (row[idx.get("Pricing Tier", -1)] if "Pricing Tier" in idx else "").strip().lower()
    if "spot" in tier:
        return True
    if "on-demand" in tier or "ondemand" in tier:
        return False
    # fallback: Notes / Experiment ID heuristics
    exp = row[idx["Experiment ID"]].lower()
    notes = row[idx.get("Notes", idx["Experiment ID"])].lower() if "Notes" in idx else ""
    if "ondemand" in exp or "on-demand" in exp or "_od_" in exp:
        return False
    if "spot" in exp or "spot" in notes:
        return True
    return True  # paper extended phase defaults Spot


def collect_succeeded(rows: list[list[str]], idx: dict[str, int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows[1:]:
        if row[idx["Status"]].strip().upper() != "SUCCEEDED":
            continue
        try:
            D = int(float(row[idx["Dataset Size (D)"]]))
            N = int(float(row[idx["Nodes (N)"]]))
        except Exception:
            continue
        cx = row[idx["SMILES Complexity"]].strip().lower()
        if cx not in {"low", "medium", "high"}:
            continue
        # Prefer Cluster Parallel (paper Table 3 target); fallback wall
        par = _f(row, idx, "Cluster Parallel (s)")
        wall = _f(row, idx, "Wall Clock (s)")
        comp = _f(row, idx, "Computation (s)")
        y = par if par is not None and par > 0 else wall
        if y is None:
            continue
        exp = row[idx["Experiment ID"]].strip()
        notes = row[idx["Notes"]].strip() if "Notes" in idx else ""
        ts = _parse_ts(row[idx["Timestamp"]])
        out.append(
            {
                "exp": exp,
                "D": D,
                "N": N,
                "cx": cx,
                "y_parallel": y,
                "computation": comp,
                "wall": wall,
                "spot": _is_spot(row, idx),
                "notes": notes,
                "replica": _replica(notes),
                "ts": ts.isoformat() if ts else None,
                "ts_dt": ts,
            }
        )
    return out


def dedupe_latest_per_replica(rows: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for r in rows:
        key = (r["exp"], r["D"], r["N"], r["cx"], r["replica"], r["spot"])
        prev = best.get(key)
        if prev is None or (r["ts_dt"] and (prev["ts_dt"] is None or r["ts_dt"] > prev["ts_dt"])):
            best[key] = r
    return list(best.values())


def pool_cell_values(
    rows: list[dict],
    *,
    complexities: set[str],
    Ds: set[int] | None,
    Ns: set[int] | None,
    spot_only: bool,
    after_ts: datetime | None,
    use_median: bool,
) -> dict[str, list[tuple[int, int, float, int]]]:
    """Return per complexity list of (D,N,y,n_reps)."""
    buckets: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        if r["cx"] not in complexities:
            continue
        if spot_only and not r["spot"]:
            continue
        if Ds is not None and r["D"] not in Ds:
            continue
        if Ns is not None and r["N"] not in Ns:
            continue
        if after_ts is not None:
            if r["ts_dt"] is None or r["ts_dt"] < after_ts:
                continue
        buckets[(r["cx"], r["D"], r["N"])].append(float(r["y_parallel"]))

    out: dict[str, list[tuple[int, int, float, int]]] = defaultdict(list)
    for (cx, D, N), vals in buckets.items():
        if not vals:
            continue
        y = float(np.median(vals)) if use_median else float(np.mean(vals))
        out[cx].append((D, N, y, len(vals)))
    for cx in out:
        out[cx].sort()
    return out


def fit_report(points: list[tuple[int, int, float, int]], model: str) -> dict:
    if len(points) < 5:
        return {"error": "too_few_points", "n": len(points)}
    D = np.array([p[0] for p in points], dtype=float)
    N = np.array([p[1] for p in points], dtype=float)
    y = np.array([p[2] for p in points], dtype=float)
    X = _design_quadratic(N, D) if model == "quadratic" else _design_dn(N, D)
    beta, r2, aic = _fit(X, y)
    rmse = _loocv_rmse(X, y)
    res: dict[str, Any] = {
        "model": model,
        "n_cells": len(points),
        "r2_in_sample": r2,
        "aic": aic,
        "loocv_rmse": rmse,
        "coeffs": {},
    }
    if model == "quadratic":
        names = ["a", "b", "c", "d", "e"]
        res["coeffs"] = {k: float(v) for k, v in zip(names, beta)}
        nstars = {}
        for d in sorted({int(x) for x in D}):
            ns = _nstar_quad(beta[1], beta[3], beta[4], float(d))
            nstars[str(d)] = None if ns is None else round(float(ns), 2)
        res["n_star"] = nstars
    else:
        res["coeffs"] = {"a": float(beta[0]), "b_D_over_N": float(beta[1]), "c_N": float(beta[2])}
    return res


def replicate_heatmap(rows: list[dict], spot_only: bool = True) -> dict:
    counts: dict[str, dict[str, int]] = defaultdict(dict)
    for r in rows:
        if spot_only and not r["spot"]:
            continue
        key = f"D{r['D']}_N{r['N']}"
        counts[r["cx"]][key] = counts[r["cx"]].get(key, 0) + 1
    summary = {}
    for cx, m in counts.items():
        vals = list(m.values())
        summary[cx] = {
            "n_cells": len(vals),
            "min": min(vals) if vals else 0,
            "median": float(np.median(vals)) if vals else 0,
            "max": max(vals) if vals else 0,
            "cells_ge_5": sum(1 for v in vals if v >= 5),
            "cells_ge_7": sum(1 for v in vals if v >= 7),
            "cells_ge_10": sum(1 for v in vals if v >= 10),
            "top": sorted(m.items(), key=lambda kv: -kv[1])[:15],
        }
    return summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "warm_keeper_cutoff_utc": WARM_KEEPER_UTC.isoformat(),
        "notes": {
            "table_clarification": (
                "Paper Table 1 = coarse R²=0.851. Table 3 = extended R²=0.442/0.675. "
                "Table 6 = interleaved vs batched D20/D40 deltas (not coefficients). "
                "User 'Table 6/7' R² values map to Table 3."
            ),
            "instance_type": (
                "Live Batch DescribeComputeEnvironments (2026-09-11, eu-central-1): "
                "chemo-ec2-worker (SPOT) and chemo-ec2-worker-ondemand (EC2) both use "
                "instanceTypes=[c5.2xlarge, c5.4xlarge, c5.9xlarge], maxvCpus=1024, "
                "minvCpus=0. Spot allocation=SPOT_PRICE_CAPACITY_OPTIMIZED; OD=BEST_FIT_PROGRESSIVE. "
                "Job containers request 4 vCPU (see job definition / experiment configs). "
                "Region: eu-central-1 (.env AWS_REGION)."
            ),
        },
    }

    # ---- 1) Coarse Table 1 reproduction from PDF transcription ----
    from src.core.model import fit_paper_table1_model, load_paper_fitted

    model = fit_paper_table1_model()
    cached = load_paper_fitted()
    report["table1_reproduction"] = {
        "script": "src/core/model.py::fit_paper_table1_model / CLI: python src/core/model.py fit-paper",
        "data": "data/paper_execution_times.json (PDF Table1+2 transcription; includes D=30000)",
        "fitted_now": {
            "a": model.a,
            "b": model.b,
            "c": model.c,
            "d": model.d,
            "e": model.e,
            "r2": model.r_squared,
            "n": model.fitted_from_n_samples,
        },
        "cached_json": {
            "a": cached.a,
            "b": cached.b,
            "c": cached.c,
            "d": cached.d,
            "e": cached.e,
            "r2": cached.r_squared,
            "n": cached.fitted_from_n_samples,
        },
        "paper_claimed_r2": 0.851,
        "matches_paper": abs((model.r_squared or 0) - 0.851) < 0.002,
    }

    # ---- Sheets ----
    sheet_rows, idx = _load_rows()
    raw = collect_succeeded(sheet_rows, idx)
    rows = dedupe_latest_per_replica(raw)
    report["sheets"] = {
        "raw_succeeded_rows": len(raw),
        "deduped_latest_per_replica": len(rows),
        "D_values": sorted({r["D"] for r in rows}),
        "N_values": sorted({r["N"] for r in rows}),
        "complexities": sorted({r["cx"] for r in rows}),
        "spot_rows": sum(1 for r in rows if r["spot"]),
        "ondemand_rows": sum(1 for r in rows if not r["spot"]),
    }

    # D=30000
    d30 = [r for r in rows if r["D"] == 30000]
    report["d30000"] = {
        "present_in_sheet": len(d30) > 0,
        "n_rows": len(d30),
        "by_cx_N": {
            f"{cx}|N{N}|{tier}": n
            for (cx, N, tier), n in Counter(
                (r["cx"], r["N"], "spot" if r["spot"] else "od") for r in d30
            ).items()
        },
        "in_paper_table1_fit": True,
        "in_paper_table3_D_grid": False,
        "reason": (
            "Paper Table 3 extended-phase D grid is {5k,10k,20k,40k,50k} — D=30k omitted "
            "from the extended pow2 Spot campaign (not statistically excluded). "
            "Coarse-grid Table 1/2 DOES include D=30k. Sheet still has paper_replication "
            "rows at D=30000 from the earlier N∈{25..185} campaign."
        ),
    }

    report["replicate_counts_spot"] = replicate_heatmap(rows, spot_only=True)

    # ---- Table 3 style refits ----
    variants = {}
    for label, after, Ds, Ns in [
        ("table3_design_all_reps_median", None, TABLE3_D, TABLE3_N),
        ("table3_design_post_warmkeeper_median", WARM_KEEPER_UTC, TABLE3_D, TABLE3_N),
        ("full_N_upto_500_D_table3_median", None, TABLE3_D, None),
        ("full_N_upto_500_all_D_spot_median", None, None, None),
        ("include_d30k_with_table3_N_median", None, TABLE3_D | {30000}, TABLE3_N),
    ]:
        pooled = pool_cell_values(
            rows,
            complexities={"low", "medium"},
            Ds=Ds,
            Ns=Ns if Ns is not None else None,
            spot_only=True,
            after_ts=after,
            use_median=True,
        )
        # If Ns is None, keep N<=500 only for high-N extension request
        if Ns is None:
            for cx in list(pooled):
                pooled[cx] = [p for p in pooled[cx] if p[1] <= 500]
        block = {}
        for cx in ("low", "medium"):
            pts = [p for p in pooled.get(cx, []) if p[3] >= 3]  # ≥3 reps like paper
            pts_all = pooled.get(cx, [])
            q = fit_report(pts, "quadratic")
            dn = fit_report(pts, "dn")
            # row-level (all replicates) quadratic
            row_pts = []
            for r in rows:
                if r["cx"] != cx or not r["spot"]:
                    continue
                if Ds is not None and r["D"] not in Ds:
                    continue
                if Ns is not None and r["N"] not in Ns:
                    continue
                if after is not None and (r["ts_dt"] is None or r["ts_dt"] < after):
                    continue
                if Ns is None and r["N"] > 500:
                    continue
                row_pts.append((r["D"], r["N"], r["y_parallel"], 1))
            q_rows = fit_report(row_pts, "quadratic") if len(row_pts) >= 5 else {"error": "too_few"}
            block[cx] = {
                "n_cells_ge3": len(pts),
                "n_cells_any": len(pts_all),
                "rep_counts_ge3": sorted({p[3] for p in pts}),
                "quadratic_median_cells_ge3": q,
                "dn_model_median_cells_ge3": dn,
                "quadratic_all_replicate_rows": q_rows,
                "paper_table3": PAPER_TABLE3[cx],
            }
        variants[label] = block

    report["refits"] = variants

    # Compare paper Table 3 R² vs best matching design
    compare = {}
    for cx in ("low", "medium"):
        got = variants["table3_design_all_reps_median"][cx]["quadratic_median_cells_ge3"]
        paper = PAPER_TABLE3[cx]
        compare[cx] = {
            "paper_r2": paper["r2"],
            "reproduced_r2": got.get("r2_in_sample"),
            "delta_r2": None
            if "r2_in_sample" not in got
            else got["r2_in_sample"] - paper["r2"],
            "paper_n_cells": paper["n"],
            "reproduced_n_cells": got.get("n_cells"),
            "reproduced_coeffs": got.get("coeffs"),
            "loocv_rmse_quadratic": got.get("loocv_rmse"),
            "loocv_rmse_dn": variants["table3_design_all_reps_median"][cx][
                "dn_model_median_cells_ge3"
            ].get("loocv_rmse"),
            "preferred_by_loocv": None,
        }
        a = compare[cx]["loocv_rmse_quadratic"]
        b = compare[cx]["loocv_rmse_dn"]
        if a is not None and b is not None:
            compare[cx]["preferred_by_loocv"] = "quadratic" if a <= b else "a+b(D/N)+cN"
    report["table3_reproduction"] = compare

    # High-N presence
    high_n = sorted({r["N"] for r in rows if r["N"] > 128})
    report["high_N_beyond_128"] = {
        "N_values_present": high_n,
        "rows": sum(1 for r in rows if r["N"] > 128),
        "note": (
            "N∈{150,185,300,500} appear mainly from paper_replication / full_pipeline "
            "campaigns, not the extended pow2 Spot grid used for Table 3."
        ),
    }

    out_json = OUT / "paper_audit_report.json"
    out_json.write_text(json.dumps(report, indent=2, default=str))

    # Human markdown
    md = []
    md.append("# Paper audit handoff report\n")
    md.append(f"Generated: `{report['generated_at_utc']}`\n")
    md.append("## Clarification on tables\n")
    md.append(report["notes"]["table_clarification"] + "\n")
    md.append("## 1) Table 1 (coarse) reproduction\n")
    t1 = report["table1_reproduction"]
    md.append(
        f"- Script: `{t1['script']}`\n"
        f"- Data: `{t1['data']}`\n"
        f"- Reproduced R² = **{t1['fitted_now']['r2']:.6f}** (paper claims 0.851)\n"
        f"- Match: **{t1['matches_paper']}**\n"
        f"- Coeffs a..e ≈ {t1['fitted_now']['a']:.3f}, {t1['fitted_now']['b']:.3f}, "
        f"{t1['fitted_now']['c']:.5f}, {t1['fitted_now']['d']:.5f}, {t1['fitted_now']['e']:.3e}\n"
    )
    md.append("## 2) Table 3 (extended) reproduction from current sheet\n")
    for cx in ("low", "medium"):
        c = compare[cx]
        md.append(
            f"### {cx}\n"
            f"- Paper R²={c['paper_r2']} (n={c['paper_n_cells']})\n"
            f"- Reproduced R²={c['reproduced_r2']} (n_cells={c['reproduced_n_cells']})\n"
            f"- ΔR²={c['delta_r2']}\n"
            f"- LOOCV RMSE quadratic={c['loocv_rmse_quadratic']} vs D/N model={c['loocv_rmse_dn']}\n"
            f"- Preferred by LOOCV: **{c['preferred_by_loocv']}**\n"
            f"- Coeffs: `{c['reproduced_coeffs']}`\n"
        )
    md.append("## 3) Warm-keeper cutoff\n")
    md.append(
        f"- Confirmed deployed **{WARM_KEEPER_UTC.isoformat()}** "
        f"(`tmp/overnight_run.log` STEP 1: minScaleDownDelayMinutes=20 on both CEs).\n"
        f"- Pilot started earlier: 2026-07-09T15:41:15Z.\n"
    )
    for cx in ("low", "medium"):
        allm = variants["table3_design_all_reps_median"][cx]["quadratic_median_cells_ge3"]
        post = variants["table3_design_post_warmkeeper_median"][cx]["quadratic_median_cells_ge3"]
        md.append(
            f"- {cx}: all-data R²={allm.get('r2_in_sample')} (n={allm.get('n_cells')}); "
            f"post-warm-keeper R²={post.get('r2_in_sample')} (n={post.get('n_cells')})\n"
        )
    md.append("## 4) D=30,000\n")
    md.append(f"- {report['d30000']['reason']}\n")
    md.append(f"- Sheet rows at D=30000: {report['d30000']['n_rows']}\n")
    md.append("## 5) Replicate counts (Spot, deduped latest/replica)\n")
    for cx, s in report["replicate_counts_spot"].items():
        md.append(
            f"- {cx}: cells={s['n_cells']}, min={s['min']}, median={s['median']}, max={s['max']}, "
            f"≥5:{s['cells_ge_5']}, ≥7:{s['cells_ge_7']}, ≥10:{s['cells_ge_10']}\n"
            f"  top: {s['top'][:8]}\n"
        )
    md.append("## 6) N beyond 128\n")
    md.append(f"- Present N>128: {report['high_N_beyond_128']['N_values_present']}\n")
    md.append(f"- {report['high_N_beyond_128']['note']}\n")
    for cx in ("low", "medium"):
        ext = variants["full_N_upto_500_D_table3_median"][cx]["quadratic_median_cells_ge3"]
        md.append(
            f"- {cx} refit allowing N≤500 on Table3 Ds: R²={ext.get('r2_in_sample')} "
            f"n={ext.get('n_cells')} N*={ext.get('n_star')}\n"
        )
    md.append("## 7) Instance type / region\n")
    md.append(report["notes"]["instance_type"] + "\n")
    md.append(f"\nFull JSON: `{out_json}`\n")

    out_md = OUT / "PAPER_AUDIT_HANDOFF.md"
    out_md.write_text("".join(md))
    print("".join(md))
    print(f"\nWrote {out_md} and {out_json}")


if __name__ == "__main__":
    main()
