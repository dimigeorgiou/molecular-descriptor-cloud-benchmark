#!/usr/bin/env python3
"""
Paper 2 Task 1–2: sheet audit, column-shift recovery, Spot cost backfill,
full_pipeline replicate-gap estimate.

Does NOT submit Batch jobs. Writes corrected dataset + provenance + estimate
and exits for human approval before Task 2 job submission.

Usage:
  PYTHONPATH=. python scripts/paper2_task1_task2_audit.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env")

OUT = REPO / "tmp" / "paper2_rebuild"
OUT.mkdir(parents=True, exist_ok=True)

REAL_D = {5000, 10000, 20000, 30000, 40000, 50000}
# Established coarse grid + extended high-N (from sheet / configs)
N_ESTABLISHED = {25, 50, 75, 100, 125, 150, 185}
# Typical high-N steps in full_pipeline_10_100 / high-N legs
N_HIGH_EXPECTED = set(range(200, 501, 25))  # 200..500 step 25


def _pf(x: Any) -> float | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(x)
    except Exception:
        return None


def _is_uuid(s: Any) -> bool:
    s = str(s or "")
    return len(s) == 36 and s.count("-") == 4


def _is_status(s: Any) -> bool:
    return str(s or "").strip().upper() in {
        "SUCCEEDED",
        "FAILED",
        "TIMEOUT",
        "UNKNOWN",
        "RUNNING",
        "SUBMITTED",
    }


def correct_row(raw: dict[str, str]) -> dict[str, Any]:
    """
    Apply known column-shift correction used for paper_replication full_pipeline
    rows written before Pricing Tier / equiv cost columns were inserted.

    Shifted layout evidence:
      Cost On-Demand Equiv ← real Job ID (UUID)
      N* Optimal           ← real Status
      Job ID               ← real Cluster Parallel-like time
      Status               ← real Wall Clock-like time
    """
    out = dict(raw)
    cod = raw.get("Cost On-Demand Equiv (USD)", "")
    nstar = raw.get("N* Optimal", "")
    job = raw.get("Job ID", "")
    status = raw.get("Status", "")
    wall = raw.get("Wall Clock (s)", "")
    par = raw.get("Cluster Parallel (s)", "")
    notes = raw.get("Notes", "")

    is_shifted = _is_uuid(cod) and str(nstar).strip().upper() == "SUCCEEDED"
    # Also treat float-in-Status + empty Wall as shifted even if UUID missing
    if not is_shifted:
        if _pf(status) is not None and not _is_status(status) and (wall == "" or wall is None):
            is_shifted = True

    if is_shifted:
        real_job = str(cod).strip() if _is_uuid(cod) else str(job).strip()
        real_status = str(nstar).strip().upper() if _is_status(nstar) else "SUCCEEDED"
        real_par = _pf(job)
        real_wall = _pf(status)
        # On-Demand equiv may be empty under shift; Cost (USD) still left-aligned
        od_equiv = None
        spot_equiv = _pf(raw.get("Cost Spot Equiv (USD)", ""))
        schema = "shifted_v1"
    else:
        real_job = str(job).strip()
        real_status = str(status).strip().upper()
        if not real_status and _is_status(notes):
            real_status = str(notes).strip().upper()
        real_par = _pf(par)
        real_wall = _pf(wall)
        od_equiv = _pf(raw.get("Cost On-Demand Equiv (USD)", ""))
        spot_equiv = _pf(raw.get("Cost Spot Equiv (USD)", ""))
        schema = "modern"

    mode = str(raw.get("Mode", "")).strip().lower()
    tier = str(raw.get("Pricing Tier", "")).strip().upper()
    cost = _pf(raw.get("Cost (USD)", ""))
    total = _pf(raw.get("Total Pipeline (s)", ""))
    comp = _pf(raw.get("Computation (s)", ""))

    try:
        D = int(float(raw.get("Dataset Size (D)", "") or 0))
        N = int(float(raw.get("Nodes (N)", "") or 0))
    except Exception:
        D, N = 0, 0

    out.update(
        {
            "schema": schema,
            "is_shifted": is_shifted,
            "RealStatus": real_status,
            "RealJobID": real_job,
            "RealClusterParallel": real_par,
            "RealWallClock": real_wall,
            "RealCostUSD": cost,
            "RealCostSpotEquiv": spot_equiv,
            "RealCostOnDemandEquiv": od_equiv,
            "RealTotalPipeline": total,
            "RealComputation": comp,
            "ModeNorm": mode,
            "PricingTierNorm": tier,
            "D": D,
            "N": N,
            "Complexity": str(raw.get("SMILES Complexity", "")).strip().lower(),
            "ExperimentID": str(raw.get("Experiment ID", "")).strip(),
            "Timestamp": str(raw.get("Timestamp", "")).strip(),
        }
    )
    return out


def try_aws_spot_price(region: str) -> dict[str, Any]:
    """Attempt Pricing API / Spot price history for c5.2xlarge in region."""
    result: dict[str, Any] = {
        "available": False,
        "method": None,
        "region": region,
        "instance_types": ["c5.2xlarge", "c5.4xlarge", "c5.9xlarge"],
        "error": None,
        "samples": [],
    }
    try:
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        # Spot price history (last ~1 day of samples)
        end = datetime.now(timezone.utc)
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        # look back 7 days
        from datetime import timedelta

        start = end - timedelta(days=7)
        prices = []
        for itype in result["instance_types"]:
            resp = ec2.describe_spot_price_history(
                InstanceTypes=[itype],
                ProductDescriptions=["Linux/UNIX"],
                StartTime=start,
                EndTime=end,
                MaxResults=20,
            )
            for p in resp.get("SpotPriceHistory", []):
                prices.append(
                    {
                        "InstanceType": p["InstanceType"],
                        "SpotPrice": float(p["SpotPrice"]),
                        "AvailabilityZone": p.get("AvailabilityZone"),
                        "Timestamp": p["Timestamp"].isoformat()
                        if hasattr(p["Timestamp"], "isoformat")
                        else str(p["Timestamp"]),
                    }
                )
        if prices:
            result["available"] = True
            result["method"] = "ec2.describe_spot_price_history"
            result["samples"] = prices[:30]
            # per-type mean
            by = defaultdict(list)
            for p in prices:
                by[p["InstanceType"]].append(p["SpotPrice"])
            result["mean_by_type"] = {k: float(np.mean(v)) for k, v in by.items()}
            # Approximate per-vCPU: c5.2xlarge=8 vCPU → use c5.2xlarge/8 as reference
            if "c5.2xlarge" in result["mean_by_type"]:
                result["spot_per_vcpu_hour_approx"] = result["mean_by_type"]["c5.2xlarge"] / 8.0
        else:
            result["error"] = "empty_spot_price_history"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def measure_od_spot_ratio(rows: list[dict]) -> dict[str, Any]:
    """Empirical OD/Spot ratio from compute_only rows with real Pricing Tier."""
    ratios = []
    for r in rows:
        if r["ModeNorm"] != "compute_only":
            continue
        if r["RealStatus"] != "SUCCEEDED":
            continue
        spot = r["RealCostSpotEquiv"]
        od = r["RealCostOnDemandEquiv"]
        # Prefer measured Cost when tier matches
        cost = r["RealCostUSD"]
        tier = r["PricingTierNorm"]
        if spot and od and spot > 0:
            ratios.append(od / spot)
        elif cost and spot and spot > 0 and "ON" in tier:
            ratios.append(cost / spot)
        elif cost and od and cost > 0 and "SPOT" in tier:
            ratios.append(od / cost)
    arr = np.array(ratios, dtype=float) if ratios else np.array([])
    return {
        "n_ratio_samples": int(len(arr)),
        "mean": float(np.mean(arr)) if len(arr) else None,
        "std": float(np.std(arr)) if len(arr) else None,
        "median": float(np.median(arr)) if len(arr) else None,
        "prompt_claimed_mean": 3.20,
        "prompt_claimed_std": 0.024,
        "prompt_claimed_n": 1022,
    }


def estimate_job_cost_usd(N: int, wall_sec: float, *, spot: bool = True) -> float:
    """Rough Batch cost: N containers × 4 vCPU × 8 GB × wall time."""
    from descriptor_cloud_benchmark.aws.pricing import PricingTier, cluster_billing_cost_usd

    return cluster_billing_cost_usd(
        N,
        4.0,
        8.0,
        wall_sec,
        tier=PricingTier.SPOT if spot else PricingTier.ON_DEMAND,
    )


def main() -> None:
    from descriptor_cloud_benchmark.monitoring.sheets import read_results_rows

    sid = os.environ.get("GOOGLE_SHEETS_ID") or "1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs"
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1"

    raw_rows = read_results_rows(sid, limit=50000)
    headers = raw_rows[0]
    corrected: list[dict[str, Any]] = []
    for row in raw_rows[1:]:
        # pad
        while len(row) < len(headers):
            row.append("")
        raw = {headers[i]: row[i] for i in range(len(headers))}
        corrected.append(correct_row(raw))

    succeeded = [r for r in corrected if r["RealStatus"] == "SUCCEEDED"]
    fp = [r for r in succeeded if r["ModeNorm"] == "full_pipeline"]
    co = [r for r in succeeded if r["ModeNorm"] == "compute_only"]

    # --- Spot price series ---
    spot_api = try_aws_spot_price(region)
    ratio_info = measure_od_spot_ratio(succeeded)

    # Fallback ratio
    ratio = ratio_info["mean"] if ratio_info["mean"] else 3.20
    backfill_method_global = (
        "aws_spot_price_history_per_vcpu"
        if spot_api.get("available") and spot_api.get("spot_per_vcpu_hour_approx")
        else "empirical_od_spot_ratio_from_compute_only"
    )

    # Backfill Spot equiv for full_pipeline (never overwrite measured Spot)
    n_backfilled = 0
    n_kept_measured = 0
    for r in corrected:
        measured_spot = r["RealCostSpotEquiv"]
        if measured_spot is not None and measured_spot > 0:
            r["CostSpotEquivModeledUSD"] = None
            r["CostSpotEquivModeledMethod"] = "not_applicable_measured_exists"
            if r["ModeNorm"] == "full_pipeline" and r["RealStatus"] == "SUCCEEDED":
                n_kept_measured += 1
            continue

        if r["ModeNorm"] != "full_pipeline" or r["RealStatus"] != "SUCCEEDED":
            r["CostSpotEquivModeledUSD"] = None
            r["CostSpotEquivModeledMethod"] = "not_applicable"
            continue

        od = r["RealCostOnDemandEquiv"]
        cost = r["RealCostUSD"]
        # Under shift, OD equiv is often missing; Cost (USD) is usually Spot-billed
        # for use_spot=true full_pipeline runs — but treat Cost as measured Spot when present.
        if cost is not None and cost > 0 and r["schema"] == "shifted_v1":
            # Cost column on Spot runs is already Spot-like measured estimate from pipeline
            r["CostSpotEquivModeledUSD"] = float(cost)
            r["CostSpotEquivModeledMethod"] = "use_Cost_USD_as_spot_estimate_shifted_row"
            n_backfilled += 1
            continue

        if od is not None and od > 0:
            r["CostSpotEquivModeledUSD"] = float(od / ratio)
            r["CostSpotEquivModeledMethod"] = (
                f"od_equiv_div_ratio_{ratio:.4f}_{backfill_method_global}"
            )
            n_backfilled += 1
            continue

        # Last resort: recompute from wall × nodes × rates
        wall = r["RealWallClock"] or r["RealTotalPipeline"]
        if wall and r["N"] > 0:
            from descriptor_cloud_benchmark.aws.pricing import PricingTier, cluster_billing_cost_usd

            r["CostSpotEquivModeledUSD"] = float(
                cluster_billing_cost_usd(
                    r["N"], 4.0, 8.0, float(wall), tier=PricingTier.SPOT
                )
            )
            r["CostSpotEquivModeledMethod"] = "recomputed_from_wall_N_pricing_py_rates"
            n_backfilled += 1
        else:
            r["CostSpotEquivModeledUSD"] = None
            r["CostSpotEquivModeledMethod"] = "unable_to_backfill"

    # --- Regime summary ---
    fp_N = sorted({r["N"] for r in fp if r["N"]})
    fp_D = sorted({r["D"] for r in fp if r["D"]})
    co_N = sorted({r["N"] for r in co if r["N"]})
    co_tiers = Counter(r["PricingTierNorm"] or "(empty)" for r in co)

    # Replicate counts full_pipeline cells (D in REAL_D, both cx)
    def cell_key(r: dict) -> tuple:
        return (r["Complexity"], r["D"], r["N"])

    fp_cells: dict[tuple, list] = defaultdict(list)
    for r in fp:
        if r["D"] not in REAL_D:
            continue
        if r["Complexity"] not in {"low", "medium"}:
            continue
        fp_cells[cell_key(r)].append(r)

    rep_counts = {k: len(v) for k, v in fp_cells.items()}
    # Split established vs high-N
    est_counts = {k: c for k, c in rep_counts.items() if k[2] <= 185}
    high_counts = {k: c for k, c in rep_counts.items() if k[2] > 185}

    def summarize_counts(d: dict) -> dict:
        if not d:
            return {"n_cells": 0}
        vals = list(d.values())
        return {
            "n_cells": len(vals),
            "min": min(vals),
            "median": float(np.median(vals)),
            "max": max(vals),
            "exactly_1": sum(1 for v in vals if v == 1),
            "ge_3": sum(1 for v in vals if v >= 3),
            "hist": dict(Counter(vals)),
        }

    # Expected high-N grid: N in observed high Ns or N_HIGH_EXPECTED, all D×cx
    observed_high_N = sorted({k[2] for k in high_counts})
    target_high_N = sorted(set(observed_high_N) | N_HIGH_EXPECTED)
    # Prefer observed high-N values from sheet for the gap (don't invent N not in campaign)
    # User said N=200..500; use union of observed and step-25
    gap_cells = []
    for cx in ("low", "medium"):
        for D in sorted(REAL_D):
            for N in target_high_N:
                have = rep_counts.get((cx, D, N), 0)
                need = max(0, 3 - have)
                if need > 0 or have > 0:
                    gap_cells.append(
                        {
                            "complexity": cx,
                            "D": D,
                            "N": N,
                            "have": have,
                            "need_to_reach_3": need,
                        }
                    )

    jobs_needed = sum(c["need_to_reach_3"] for c in gap_cells)
    cells_needing = [c for c in gap_cells if c["need_to_reach_3"] > 0]

    # Cost/time estimate: use median RealWallClock (or Total) per N from existing high-N or scaled
    wall_by_N: dict[int, list[float]] = defaultdict(list)
    for r in fp:
        w = r["RealWallClock"] or r["RealTotalPipeline"]
        if w and r["N"] > 185:
            wall_by_N[r["N"]].append(float(w))
    # fallback from N<=185: rough linear-ish in N for cluster init heavy
    wall_by_N_low: dict[int, list[float]] = defaultdict(list)
    for r in fp:
        w = r["RealWallClock"] or r["RealTotalPipeline"]
        if w and r["N"] <= 185:
            wall_by_N_low[r["N"]].append(float(w))

    def predict_wall(N: int) -> float:
        if N in wall_by_N and wall_by_N[N]:
            return float(np.median(wall_by_N[N]))
        if wall_by_N:
            # nearest observed high N
            nearest = min(wall_by_N.keys(), key=lambda x: abs(x - N))
            return float(np.median(wall_by_N[nearest]))
        if wall_by_N_low:
            # scale from N=185 median
            base_n = max(wall_by_N_low.keys())
            base = float(np.median(wall_by_N_low[base_n]))
            return base * (N / base_n)
        return 300.0  # conservative default seconds

    est_cost_spot = 0.0
    est_wall_serial_sec = 0.0
    for c in cells_needing:
        w = predict_wall(c["N"])
        for _ in range(c["need_to_reach_3"]):
            est_cost_spot += estimate_job_cost_usd(c["N"], w, spot=True)
            est_wall_serial_sec += w + 60.0  # +queue slack

    # Parallelism assumption: Batch can run many jobs; with maxvCpus=1024 and 4 vCPU/job → 256 concurrent
    # But large N jobs need N*4 vCPUs each — bottleneck is CE maxvCpus
    # For N=500 → 2000 vCPU needed > 1024 → cannot run one N=500 job on current max?
    # Actually each "job" in this codebase is one experiment that launches N workers — need to check.
    # From prior context: one Batch job = one (D,N) cell with N containers. So vCPUs = N*4.
    # maxvCpus=1024 → max N = 256. N=300..500 would need CE bump!
    max_n_on_1024 = 1024 // 4
    oversized = sorted({c["N"] for c in cells_needing if c["N"] * 4 > 1024})

    # Concurrent estimate: jobs with N<=128 can pack; large N serialize
    concurrent_cap_jobs_at_n = lambda n: max(1, 1024 // (n * 4)) if n * 4 <= 1024 else 0

    estimate = {
        "jobs_needed_to_reach_3_reps": jobs_needed,
        "cells_needing_jobs": len(cells_needing),
        "target_high_N_values": target_high_N,
        "observed_high_N_values": observed_high_N,
        "estimated_spot_cost_usd": round(est_cost_spot, 2),
        "estimated_serial_wall_hours": round(est_wall_serial_sec / 3600.0, 2),
        "notes": [
            "Cost uses src.aws.pricing Spot rates × N × 4 vCPU × 8 GB × predicted wall.",
            "Wall prediction = median RealWallClock of existing same-N full_pipeline rows when available.",
            "Serial wall is upper bound; actual calendar time depends on Batch concurrency.",
            f"CE maxvCpus=1024 ⇒ max N per single cell job ≈ {max_n_on_1024} (4 vCPU/node). "
            f"N values needing CE bump or multi-CE: {oversized}",
        ],
        "ce_max_n_without_bump": max_n_on_1024,
        "n_values_exceeding_ce_capacity": oversized,
        "approval_required": True,
        "do_not_submit_until": "explicit user approval of this estimate",
    }

    # --- Write corrected CSV ---
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
        "Avg SMILES Length",
        "Dataset Size (MB)",
        "S3 Upload (s)",
        "Cluster Init (s)",
        "Scheduling (s)",
        "Sync Overhead (s)",
        "Result Upload (s)",
        "Notes",
    ]
    csv_path = OUT / "corrected_sheet_succeeded_and_all.csv"
    # Write ALL corrected rows (incl failed) for provenance; also succeeded-only
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        w.writeheader()
        for r in corrected:
            row = {k: r.get(k, r.get(k, "")) for k in out_cols}
            # fill original metric cols from raw keys if present
            for k in out_cols:
                if k not in r and k in r:
                    row[k] = r[k]
            # map original headers still on r
            for orig in (
                "Avg SMILES Length",
                "Dataset Size (MB)",
                "S3 Upload (s)",
                "Cluster Init (s)",
                "Scheduling (s)",
                "Sync Overhead (s)",
                "Result Upload (s)",
                "Notes",
            ):
                row[orig] = r.get(orig, "")
            w.writerow(row)

    succ_csv = OUT / "corrected_sheet_succeeded.csv"
    with succ_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        w.writeheader()
        for r in succeeded:
            row = {k: r.get(k, "") for k in out_cols}
            for orig in (
                "Avg SMILES Length",
                "Dataset Size (MB)",
                "S3 Upload (s)",
                "Cluster Init (s)",
                "Scheduling (s)",
                "Sync Overhead (s)",
                "Result Upload (s)",
                "Notes",
            ):
                row[orig] = r.get(orig, "")
            w.writerow(row)

    gap_csv = OUT / "task2_replicate_gap_cells.csv"
    with gap_csv.open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["complexity", "D", "N", "have", "need_to_reach_3"]
        )
        w.writeheader()
        for c in sorted(cells_needing, key=lambda x: (x["complexity"], x["D"], x["N"])):
            w.writerow(c)

    # Provenance
    provenance = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sheet_id": sid,
        "region": region,
        "n_raw_rows": len(corrected),
        "n_succeeded": len(succeeded),
        "n_full_pipeline_succeeded": len(fp),
        "n_compute_only_succeeded": len(co),
        "n_shifted_rows": sum(1 for r in corrected if r["is_shifted"]),
        "column_shift_rule": (
            "is_shifted if Cost On-Demand Equiv looks like UUID and N* Optimal==SUCCEEDED, "
            "or Status is numeric and Wall Clock empty. Then RealJobID←COD, RealStatus←N*, "
            "RealClusterParallel←Job ID, RealWallClock←Status."
        ),
        "spot_backfill": {
            "aws_spot_price_check": spot_api,
            "empirical_od_spot_ratio": ratio_info,
            "ratio_used": ratio,
            "method_selected": backfill_method_global,
            "n_full_pipeline_backfilled": n_backfilled,
            "n_full_pipeline_kept_measured_spot": n_kept_measured,
            "new_columns": [
                "CostSpotEquivModeledUSD",
                "CostSpotEquivModeledMethod",
            ],
            "never_overwrites": ["RealCostSpotEquiv", "Cost Spot Equiv (USD)"],
        },
        "regimes": {
            "full_pipeline": {
                "N_values": fp_N,
                "D_values": fp_D,
                "n_rows": len(fp),
                "complexity": dict(Counter(r["Complexity"] for r in fp)),
            },
            "compute_only": {
                "N_values": co_N,
                "n_rows": len(co),
                "pricing_tiers": dict(co_tiers),
            },
        },
        "replicate_audit": {
            "established_N_le_185": summarize_counts(est_counts),
            "high_N_gt_185": summarize_counts(high_counts),
            "high_N_cells_exactly_1": sum(1 for v in high_counts.values() if v == 1),
            "high_N_cells_ge_3": sum(1 for v in high_counts.values() if v >= 3),
        },
        "task2_estimate": estimate,
        "outputs": {
            "corrected_all": str(csv_path.relative_to(REPO)),
            "corrected_succeeded": str(succ_csv.relative_to(REPO)),
            "gap_cells": str(gap_csv.relative_to(REPO)),
        },
        "task3_blocked_until": "Task 2 replicate jobs approved and completed; cells with <3 reps excluded",
    }
    prov_path = OUT / "DATA_PROVENANCE.json"
    prov_path.write_text(json.dumps(provenance, indent=2, default=str))

    # Human markdown gate
    md = []
    md.append("# Paper 2 — Task 1–2 audit (STOP for approval)\n\n")
    md.append(f"Generated: `{provenance['generated_at_utc']}`\n\n")
    md.append("**AI Risk Assessment: medium** — Sheets write not performed; Batch jobs NOT submitted.\n\n")
    md.append("## Task 1 — regimes + Spot backfill\n\n")
    md.append(f"- Raw rows corrected: **{len(corrected)}** (shifted: {provenance['n_shifted_rows']})\n")
    md.append(f"- SUCCEEDED: **{len(succeeded)}** · full_pipeline: **{len(fp)}** · compute_only: **{len(co)}**\n")
    md.append(f"- full_pipeline N range: {fp_N[0] if fp_N else None}…{fp_N[-1] if fp_N else None} ({len(fp_N)} distinct)\n")
    md.append(f"- compute_only N max: {max(co_N) if co_N else None}; tiers: `{dict(co_tiers)}`\n")
    md.append(f"- AWS Spot price history: available={spot_api.get('available')} method={spot_api.get('method')} err={spot_api.get('error')}\n")
    md.append(f"- Empirical OD/Spot ratio: n={ratio_info['n_ratio_samples']} mean={ratio_info['mean']} std={ratio_info['std']}\n")
    md.append(f"- Backfill method selected: **{backfill_method_global}** (ratio={ratio:.4f})\n")
    md.append(f"- Modeled Spot column fills: **{n_backfilled}** (measured Spot preserved: {n_kept_measured})\n\n")
    md.append("## Task 2 — replicate gap (full_pipeline, D∈{5…50}k)\n\n")
    md.append(f"- Established N≤185: `{summarize_counts(est_counts)}`\n")
    md.append(f"- High N>185: `{summarize_counts(high_counts)}`\n")
    md.append(f"- High-N cells with exactly 1 rep: **{sum(1 for v in high_counts.values() if v == 1)}**\n\n")
    md.append("### Jobs required to reach ≥3 reps (N>185 target grid)\n\n")
    md.append(f"- **Jobs to submit: {jobs_needed}** across **{len(cells_needing)}** cells\n")
    md.append(f"- **Estimated Spot cost: ${estimate['estimated_spot_cost_usd']:.2f}**\n")
    md.append(f"- **Estimated serial wall: ~{estimate['estimated_serial_wall_hours']:.1f} h** (upper bound)\n")
    md.append(f"- CE capacity issue: N>{max_n_on_1024} need maxvCpus bump: `{oversized}`\n\n")
    md.append("### STOP — awaiting explicit approval\n\n")
    md.append("Reply with e.g. `Yes, I approve submitting the Task 2 replicate jobs` "
              "(and whether to bump CE maxvCpus for N>256) before any Batch submission.\n\n")
    md.append("Tasks 3–5 are **blocked** until replicates land.\n\n")
    md.append("## Outputs\n\n")
    md.append(f"- `{csv_path.relative_to(REPO)}`\n")
    md.append(f"- `{succ_csv.relative_to(REPO)}`\n")
    md.append(f"- `{gap_csv.relative_to(REPO)}`\n")
    md.append(f"- `{prov_path.relative_to(REPO)}`\n")

    (OUT / "TASK1_TASK2_GATE.md").write_text("".join(md))
    print("".join(md))


if __name__ == "__main__":
    main()
