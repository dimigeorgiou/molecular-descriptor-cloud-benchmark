"""
Main experiment runner.

Supports:
  - AWS Batch mode (no --local): upload dataset to S3, submit Batch jobs, log to Google Sheets Results tab.
  - Local mode (--local): run the worker directly on this machine; same sheet (GOOGLE_SHEETS_ID → Results).

Each invocation (with or without ``--config``) creates a timestamped folder under
``experiments/results/<name>_<timestamp>/``, copies the effective YAML to ``config.yaml``,
writes ``estimation/estimate.json`` (pre-run estimator snapshot) unless skipped, then
writes ``batch_*.json`` / ``local_*.json`` and optional plot PNGs there.

After a successful AWS Batch run (or ``--local``), when a pre-run estimate exists,
``verification_report.json`` is written in the same folder (estimate vs actual,
including cost and total-pipeline loss blocks and a one-row summary for tooling).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import boto3
import yaml
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

from src.core.batch_timing import derive_batch_array_timings, max_shard_wallclock_sec
from src.core.timer import ExperimentTimer
from src.aws.batch_manager import BatchJobConfig, resolve_batch_queue, submit_batch_job
from src.aws.pricing import (
    PricingTier,
    container_runtime_cost_usd,
    tier_from_use_spot,
    tier_label,
)
from src.monitoring.sheets import append_timing_result

from experiments.verify_estimate_vs_actual import (
    _summarize_multi_report,
    compare_runs,
)

def load_config(path: Path) -> Dict[str, Any]:
    """Load an experiment YAML configuration."""
    with open(path) as f:
        return yaml.safe_load(f)


def _resolve_grid_pairs(cfg: Dict[str, Any]) -> List[tuple[int, int]]:
    """
    Return (D, N) cells to run.

    If ``grid_pairs`` is set, use explicit pairs only (no cross-product).
    Otherwise cross-product dataset_sizes × node_configs.
    """
    raw = cfg.get("grid_pairs")
    if raw:
        pairs: List[tuple[int, int]] = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                pairs.append((int(item[0]), int(item[1])))
            elif isinstance(item, dict):
                pairs.append((int(item["dataset_size"]), int(item["n_nodes"])))
            else:
                raise ValueError(f"Invalid grid_pairs entry: {item!r}")
        return pairs
    dataset_sizes: List[int] = cfg.get("dataset_sizes", [])
    node_configs: List[int] = cfg.get("node_configs", [])
    return [(d, n) for d in dataset_sizes for n in node_configs]


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _write_pre_run_estimate(
    config_path: Path,
    results_root: Path,
    dataset_dir: Path | None = None,
) -> Path:
    """
    Run the analytical estimator once and save JSON under results_root/estimation/.

    This pairs with verify_estimate_vs_actual.py (--run-dir discovers estimate.json).
    """
    from src.core.model import ModelCoefficients, load_paper_fitted

    cfg = load_config(config_path)
    try:
        model = load_paper_fitted()
        logger.info(
            "Pre-run estimate using paper_fitted model (R²={})",
            model.r_squared,
        )
    except FileNotFoundError:
        model = ModelCoefficients.placeholder_defaults()
        logger.warning(
            "Pre-run estimate using placeholder_defaults (NOT paper Table 1 fit)"
        )
    from experiments.estimator.experiment_estimator import run_estimator

    summary = run_estimator(
        cfg,
        model,
        verbose=False,
        dataset_dir=dataset_dir,
    )
    summary["frozen_config_path"] = str(config_path.resolve())
    summary["estimate_written_at_utc"] = datetime.utcnow().isoformat() + "Z"

    est_dir = results_root / "estimation"
    est_dir.mkdir(parents=True, exist_ok=True)
    out_path = est_dir / "estimate.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Pre-run estimate saved → {}", out_path)
    return out_path


def _write_verification_report(
    results_root: Path,
    actual_json: Path,
    *,
    metric: str = "auto",
) -> Path | None:
    """
    Compare ``estimation/estimate.json`` to the completed ``batch_*.json`` / ``local_*.json``.

    Writes ``verification_report.json`` (multi-run-shaped payload with one ``runs`` entry
    plus ``summary_table_rows``) for dashboards and CLI follow-up.
    """
    estimate_path = results_root / "estimation" / "estimate.json"
    if not estimate_path.is_file():
        logger.info("Skipping verification: missing {}", estimate_path)
        return None
    try:
        with open(estimate_path) as f:
            est_data: Dict[str, Any] = json.load(f)
        with open(actual_json) as f:
            act_raw: Any = json.load(f)
    except OSError as exc:
        logger.warning("Verification skipped (could not read JSON): {}", exc)
        return None

    if isinstance(act_raw, list):
        actual_rows: List[Dict[str, Any]] = act_raw
    elif isinstance(act_raw, dict) and "runs" in act_raw:
        actual_rows = act_raw["runs"]
    else:
        logger.warning("Skipping verification: actual JSON is not a list or {{runs: []}}")
        return None
    if not actual_rows:
        logger.warning("Skipping verification: actual result list is empty")
        return None

    try:
        report = compare_runs(est_data, actual_rows, metric=metric)
        report_cost = compare_runs(est_data, actual_rows, metric="cost_usd")
        report_tp = compare_runs(est_data, actual_rows, metric="total_pipeline_sec")
    except Exception as exc:  # pragma: no cover - estimator / schema drift
        logger.warning("Verification compare failed: {}", exc)
        return None

    multi_report: Dict[str, Any] = {
        "metric_arg": metric,
        "fixed_estimate_path": str(estimate_path.resolve()),
        "runs": [
            {
                "run_dir": str(results_root.resolve()),
                "estimate_path": str(estimate_path.resolve()),
                "actual_path": str(actual_json.resolve()),
                "report": report,
                "report_cost": report_cost,
                "report_total_pipeline": report_tp,
            }
        ],
    }
    multi_report["summary_table_rows"] = _summarize_multi_report(multi_report)

    out_path = results_root / "verification_report.json"
    with open(out_path, "w") as f:
        json.dump(multi_report, f, indent=2)
    logger.success("Verification report → {}", out_path)
    return out_path


def _compute_dataset_stats(csv_path: Path) -> Dict[str, Any]:
    import pandas as pd

    df = pd.read_csv(csv_path)
    smiles_col = df["smiles"].astype(str)
    avg_len = float(smiles_col.str.len().mean())
    size_mb = csv_path.stat().st_size / (1024 * 1024)
    return {
        "smiles_avg_length": round(avg_len, 3),
        "dataset_size_mb": round(size_mb, 3),
    }


def _save_experiment_plots(
    results: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    output_dir: Path,
) -> None:
    """
    Save rich visualizations for a finished experiment run.

    We generate several PNGs:
      - panel_overview.png    → high-level execution + cost + breakdown + scaling
      - panel_phases.png      → detailed phase comparisons and ratios
      - panel_efficiency.png  → speedup, cost-efficiency, and cost vs time
    """
    if not results:
        return

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning(
            "matplotlib not installed; skipping visualization panels for this run."
        )
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Flatten some basic metrics
    labels: List[str] = []
    exec_times: List[float] = []
    costs: List[float] = []
    n_nodes: List[int] = []
    dataset_sizes: List[int] = []
    s3_times: List[float] = []
    comp_times: List[float] = []
    sync_times: List[float] = []
    total_times: List[float] = []

    for r in results:
        d = int(r.get("dataset_size", 0))
        n = int(r.get("n_nodes", 0))
        label = f"D{d}_N{n}"
        labels.append(label)
        exec_times.append(float(r.get("computation_sec", 0.0)))
        costs.append(float(r.get("cost_usd", 0.0)))
        n_nodes.append(n)
        dataset_sizes.append(d)
        s3_times.append(float(r.get("s3_upload_sec", 0.0)))
        comp_times.append(float(r.get("computation_sec", 0.0)))
        sync_times.append(float(r.get("sync_overhead_sec", 0.0)))
        total_times.append(float(r.get("total_pipeline_sec", 0.0)))

    x = range(len(labels))

    # ---------- Panel 1: high-level overview ----------
    fig1, axes1 = plt.subplots(2, 2, figsize=(12, 8))
    fig1.suptitle(cfg.get("name", "experiment"), fontsize=14)

    # 1A: Execution time per (D,N)
    ax = axes1[0, 0]
    ax.bar(x, exec_times, color="#4c72b0")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Computation (s)")
    ax.set_title("Execution time per configuration")

    # 1B: Cost per (D,N)
    ax = axes1[0, 1]
    ax.bar(x, costs, color="#55a868")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Cost (USD)")
    ax.set_title("Estimated cost per configuration")

    # 1C: Phase breakdown (stacked bars)
    ax = axes1[1, 0]
    ax.bar(x, s3_times, label="S3 upload", color="#4c72b0")
    ax.bar(x, comp_times, bottom=s3_times, label="Computation", color="#dd8452")
    bottom_sync = [s3 + comp for s3, comp in zip(s3_times, comp_times)]
    ax.bar(x, sync_times, bottom=bottom_sync, label="Sync overhead", color="#8172b3")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Seconds")
    ax.set_title("Phase breakdown")
    ax.legend(fontsize=8)

    # 1D: n_nodes vs total pipeline time (scatter, colored by D)
    ax = axes1[1, 1]
    scatter = ax.scatter(n_nodes, total_times, c=dataset_sizes, cmap="viridis")
    ax.set_xlabel("Nodes (N)")
    ax.set_ylabel("Total pipeline (s)")
    ax.set_title("Scaling of total time with N")
    cbar = fig1.colorbar(scatter, ax=ax)
    cbar.set_label("Dataset size (D)")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    panel1_path = output_dir / "panel_overview.png"
    fig1.savefig(panel1_path, dpi=150)
    plt.close(fig1)
    logger.info("Saved visualization panel → {}", panel1_path)

    # ---------- Panel 2: detailed phase analysis ----------
    fig2, axes2 = plt.subplots(2, 2, figsize=(12, 8))
    fig2.suptitle(f"{cfg.get('name', 'experiment')} – phases", fontsize=14)

    # 2A: Total pipeline vs (D,N)
    ax = axes2[0, 0]
    ax.bar(x, total_times, color="#4c72b0")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Total pipeline (s)")
    ax.set_title("Total pipeline per configuration")

    # 2B: Overhead fraction (sync + upload) of total
    overhead = [
        (s3 + sync) / t if t > 0 else 0.0
        for s3, sync, t in zip(s3_times, sync_times, total_times)
    ]
    ax = axes2[0, 1]
    ax.bar(x, overhead, color="#dd8452")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Overhead fraction")
    ax.set_title("Upload + sync overhead / total")

    # 2C: S3 upload vs dataset size
    ax = axes2[1, 0]
    ax.scatter(dataset_sizes, s3_times, color="#4c72b0")
    ax.set_xlabel("Dataset size (D)")
    ax.set_ylabel("S3 upload (s)")
    ax.set_title("Upload time vs dataset size")

    # 2D: Computation vs dataset size, annotated by N
    ax = axes2[1, 1]
    ax.scatter(dataset_sizes, comp_times, c=n_nodes, cmap="viridis")
    for d, ctime, n in zip(dataset_sizes, comp_times, n_nodes):
        ax.annotate(str(n), (d, ctime), textcoords="offset points", xytext=(2, 2), fontsize=7)
    ax.set_xlabel("Dataset size (D)")
    ax.set_ylabel("Computation (s)")
    ax.set_title("Computation vs D, annotated by N")
    cbar2 = fig2.colorbar(
        plt.cm.ScalarMappable(cmap="viridis"),
        ax=axes2[1, 1],
        fraction=0.046,
        pad=0.04,
    )
    cbar2.set_label("Nodes (N)")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    panel2_path = output_dir / "panel_phases.png"
    fig2.savefig(panel2_path, dpi=150)
    plt.close(fig2)
    logger.info("Saved visualization panel → {}", panel2_path)

    # ---------- Panel 3: efficiency & cost metrics ----------
    fig3, axes3 = plt.subplots(2, 2, figsize=(12, 8))
    fig3.suptitle(f"{cfg.get('name', 'experiment')} – efficiency", fontsize=14)

    # Compute speedup and cost-efficiency per dataset size
    speedups: List[float] = []
    cost_per_mol: List[float] = []
    for r, t, cost in zip(results, total_times, costs):
        D = float(r.get("dataset_size", 0))
        N = int(r.get("n_nodes", 0))
        # Baseline is min total time for this D across all N.
        same_D = [tt for rr, tt in zip(results, total_times) if int(rr.get("dataset_size", 0)) == int(D)]
        baseline = min(same_D) if same_D else t or 1.0
        speedups.append(baseline / t if t > 0 else 0.0)
        cost_per_mol.append(cost / D if D > 0 else 0.0)

    # 3A: Speedup vs N (for all D)
    ax = axes3[0, 0]
    ax.scatter(n_nodes, speedups, c=dataset_sizes, cmap="viridis")
    ax.set_xlabel("Nodes (N)")
    ax.set_ylabel("Speedup vs best for D")
    ax.set_title("Parallel speedup")
    cbar3 = fig3.colorbar(
        plt.cm.ScalarMappable(cmap="viridis"),
        ax=ax,
        fraction=0.046,
        pad=0.04,
    )
    cbar3.set_label("Dataset size (D)")

    # 3B: Cost per molecule
    ax = axes3[0, 1]
    ax.bar(x, cost_per_mol, color="#55a868")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Cost per molecule (USD)")
    ax.set_title("Cost efficiency")

    # 3C: Cost vs total time (trade-off curve)
    ax = axes3[1, 0]
    ax.scatter(total_times, costs, c=n_nodes, cmap="plasma")
    ax.set_xlabel("Total pipeline (s)")
    ax.set_ylabel("Cost (USD)")
    ax.set_title("Cost vs time")
    cbar4 = fig3.colorbar(
        plt.cm.ScalarMappable(cmap="plasma"),
        ax=ax,
        fraction=0.046,
        pad=0.04,
    )
    cbar4.set_label("Nodes (N)")

    # 3D: Nodes vs cost per second (cost / total time)
    cost_per_sec = [
        (c / t) if t > 0 else 0.0
        for c, t in zip(costs, total_times)
    ]
    ax = axes3[1, 1]
    ax.scatter(n_nodes, cost_per_sec, c=dataset_sizes, cmap="viridis")
    ax.set_xlabel("Nodes (N)")
    ax.set_ylabel("Cost per second (USD/s)")
    ax.set_title("Instantaneous cost rate by N")
    cbar5 = fig3.colorbar(
        plt.cm.ScalarMappable(cmap="viridis"),
        ax=ax,
        fraction=0.046,
        pad=0.04,
    )
    cbar5.set_label("Dataset size (D)")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    panel3_path = output_dir / "panel_efficiency.png"
    fig3.savefig(panel3_path, dpi=150)
    plt.close(fig3)
    logger.info("Saved visualization panel → {}", panel3_path)


def _fetch_shard_wallclocks(
    s3_client: Any,
    *,
    bucket: str,
    shards_prefix: str,
    n_shards: int,
) -> list[float]:
    """Download shard result JSONs from S3 and return wallclock_sec per shard."""
    wallclocks: list[float] = []
    prefix = shards_prefix.rstrip("/")
    for i in range(n_shards):
        key = f"{prefix}/results/shard_{i}.json"
        try:
            obj = s3_client.get_object(Bucket=bucket, Key=key)
            payload = json.loads(obj["Body"].read().decode("utf-8"))
            wall = float(
                payload.get("wallclock_sec") or payload.get("execution_time") or 0.0
            )
            wallclocks.append(wall)
        except Exception as exc:
            logger.debug("No shard result at s3://{}/{} ({})", bucket, key, exc)
    return wallclocks


def _wait_for_single_batch_job(
    *,
    batch: Any,
    job_id: str,
    poll_interval: float = 10.0,
    timeout_sec: float = 4 * 3600.0,
    submit_ts_sec: float | None = None,
    running_deadline_sec: float | None = None,
) -> List[Dict[str, Any]]:
    """
    Poll a non-array Batch job (N=1) until SUCCEEDED or FAILED.

    submit_batch_job omits arrayProperties when n_nodes==1, so list_jobs(arrayJobId=...)
    never finds children — this path uses describe_jobs on the parent only.
    """
    waited = 0.0
    last_desc: List[Dict[str, Any]] = []

    while waited < timeout_sec:
        desc = batch.describe_jobs(jobs=[job_id]).get("jobs", [])
        if desc:
            last_desc = desc
            status = desc[0].get("status")
            if status == "SUCCEEDED":
                logger.info("Single Batch job {} SUCCEEDED", job_id)
                return desc
            if status == "FAILED":
                logger.error("Single Batch job {} FAILED", job_id)
                return desc

            if (
                running_deadline_sec
                and submit_ts_sec is not None
                and (time.time() - float(submit_ts_sec)) > float(running_deadline_sec)
                and status not in {"RUNNING", "STARTING", "SUCCEEDED"}
            ):
                logger.error(
                    "Single job {}: not RUNNING within {:.0f}s — marking TIMEOUT",
                    job_id,
                    running_deadline_sec,
                )
                job = dict(desc[0])
                job["status"] = "TIMEOUT"
                return [job]

        time.sleep(poll_interval)
        waited += poll_interval

    logger.error(
        "Timed out waiting for single Batch job {} after {} seconds",
        job_id,
        timeout_sec,
    )
    return last_desc


def _wait_for_array_job_cluster(
    *,
    batch: Any,
    parent_job_id: str,
    expected_size: int,
    poll_interval: float = 10.0,
    timeout_sec: float = 4 * 3600.0,
    submit_ts_sec: float | None = None,
    running_deadline_sec: float | None = None,
) -> List[Dict[str, Any]]:
    """
    Poll an AWS Batch array job until all child jobs finish.

    Returns a list of describe_jobs entries, one per child job.
    For expected_size==1, delegates to _wait_for_single_batch_job (non-array submit).
    """
    if expected_size <= 1:
        return _wait_for_single_batch_job(
            batch=batch,
            job_id=parent_job_id,
            poll_interval=poll_interval,
            timeout_sec=timeout_sec,
            submit_ts_sec=submit_ts_sec,
            running_deadline_sec=running_deadline_sec,
        )

    waited = 0.0
    child_descriptions: List[Dict[str, Any]] = []

    # AWS Batch list_jobs requires a jobStatus filter; default is SUBMITTED.
    # To track children across their full lifecycle we aggregate over all states.
    job_statuses = [
        "SUBMITTED",
        "PENDING",
        "RUNNABLE",
        "STARTING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
    ]

    while waited < timeout_sec:
        # If the parent has already failed, we can stop early.
        parent_desc = batch.describe_jobs(jobs=[parent_job_id]).get("jobs", [])
        if parent_desc:
            parent_status = parent_desc[0].get("status")
            if parent_status == "FAILED":
                logger.error("Array parent job {} failed", parent_job_id)
                return parent_desc

        # List child jobs belonging to this array job, across all statuses.
        child_ids: List[str] = []
        for status in job_statuses:
            next_token: str | None = None
            while True:
                if next_token:
                    listed = batch.list_jobs(
                        arrayJobId=parent_job_id,
                        jobStatus=status,
                        nextToken=next_token,
                    )
                else:
                    listed = batch.list_jobs(
                        arrayJobId=parent_job_id,
                        jobStatus=status,
                    )
                child_ids.extend(
                    j["jobId"] for j in listed.get("jobSummaryList", [])
                )
                next_token = listed.get("nextToken")
                if not next_token:
                    break

        # Dedupe while preserving order (AWS DescribeJobs rejects duplicates).
        if child_ids:
            child_ids = list(dict.fromkeys(child_ids))

        if len(child_ids) >= expected_size:
            # Describe children in chunks of up to 100 job IDs.
            all_desc: List[Dict[str, Any]] = []
            for i in range(0, len(child_ids), 100):
                chunk = child_ids[i : i + 100]
                desc = batch.describe_jobs(jobs=chunk)
                all_desc.extend(desc.get("jobs", []))

            statuses = {j.get("status") for j in all_desc}
            if statuses <= {"SUCCEEDED"}:
                logger.info(
                    "All {} child jobs for array {} SUCCEEDED", len(all_desc), parent_job_id
                )
                return all_desc
            if "FAILED" in statuses and "RUNNING" not in statuses and "STARTING" not in statuses:
                logger.error(
                    "Some child jobs for array {} FAILED (statuses={})",
                    parent_job_id,
                    statuses,
                )
                return all_desc

            child_descriptions = all_desc

        # Optional: fail fast if no child reaches RUNNING within deadline (overnight runs).
        if (
            running_deadline_sec
            and submit_ts_sec is not None
            and child_descriptions
            and (time.time() - float(submit_ts_sec)) > float(running_deadline_sec)
        ):
            active = {
                j.get("status")
                for j in child_descriptions
                if j.get("status") in {"RUNNING", "STARTING", "SUCCEEDED"}
            }
            if not active:
                logger.error(
                    "Array {}: no child RUNNING within {:.0f}s — marking TIMEOUT",
                    parent_job_id,
                    running_deadline_sec,
                )
                for j in child_descriptions:
                    if j.get("status") in {"SUBMITTED", "PENDING", "RUNNABLE"}:
                        j["status"] = "TIMEOUT"
                return child_descriptions

        time.sleep(poll_interval)
        waited += poll_interval

    logger.error(
        "Timed out waiting for array job {} children after {} seconds",
        parent_job_id,
        timeout_sec,
    )
    return child_descriptions


def run_local_experiment(
    config_path: Path,
    override_mode: str | None = None,
    dataset_dir: Path | None = None,
    results_root: Path | None = None,
) -> Path:
    """
    Run a small subset of the experiment locally (no AWS).

    Uses dataset_sizes and node_configs from config. Dataset CSVs are looked up as
    {dataset_dir}/smiles_{d}_{smiles_complexity}.csv; if dataset_dir is None,
    defaults to datasets/samples.
    """
    from src.worker.compute_descriptors import run_compute

    cfg = load_config(config_path)
    mode = override_mode or cfg.get("mode", "compute_only")
    complexity = cfg.get("smiles_complexity", "medium")

    dataset_sizes: List[int] = cfg.get("dataset_sizes", [5000])
    node_configs: List[int] = cfg.get("node_configs", [25, 50])

    base_dir = dataset_dir or Path("datasets/samples")

    results: List[Dict[str, Any]] = []
    results_dir = results_root or Path("experiments/results")
    out_path = results_dir / f"local_{mode}_{_timestamp()}.json"

    sheet_id = os.getenv("GOOGLE_SHEETS_ID")

    for d in tqdm(dataset_sizes, desc="Datasets", unit="D"):
        dataset_csv = base_dir / f"smiles_{d}_{complexity}.csv"
        if not dataset_csv.exists():
            raise FileNotFoundError(
                f"Expected dataset file not found: {dataset_csv}. "
                "Run the SMILES generator first."
            )

        stats = _compute_dataset_stats(dataset_csv)

        for n in tqdm((node_configs or [0]), desc=f"D={d} nodes", unit="config", leave=False):
            with ExperimentTimer() as timer:
                timer.set_metadata(
                    dataset_size_mb=stats["dataset_size_mb"],
                    smiles_avg_length=stats["smiles_avg_length"],
                    smiles_complexity=cfg.get("smiles_complexity", "medium"),
                )

                # --- Simulate / run phases locally according to mode ---
                # s3_upload_sec
                if mode in {"upload_only", "full_pipeline"}:
                    simulated = stats["dataset_size_mb"] / 10.0
                    with timer.phase("s3_upload_sec"):
                        time.sleep(0.0)  # we just record the simulated value
                    timer._phase_times["s3_upload_sec"] = round(simulated, 3)  # type: ignore[attr-defined]

                # cluster_init_sec
                if mode in {"compute_only", "full_pipeline"}:
                    simulated_cluster = random.uniform(30, 90)
                    timer._phase_times["cluster_init_sec"] = round(simulated_cluster, 3)  # type: ignore[attr-defined]

                # scheduling_sec
                if mode in {"compute_only", "full_pipeline"}:
                    simulated_sched = random.uniform(5, 15)
                    timer._phase_times["scheduling_sec"] = round(simulated_sched, 3)  # type: ignore[attr-defined]

                # computation_sec (real local worker)
                if mode in {"compute_only", "full_pipeline"}:
                    tmp_out = results_dir / f"local_tmp_D{d}_N{n or 1}.json"
                    descriptor_method = cfg.get("descriptor_method", "default")
                    with timer.phase("computation_sec"):
                        run_compute(
                            dataset_path=dataset_csv,
                            n_nodes=n or 1,
                            dataset_size=d,
                            output_path=tmp_out,
                            smiles_complexity=cfg.get("smiles_complexity", "medium"),
                            descriptor_method=descriptor_method,
                        )
                    with open(tmp_out) as f:
                        res = json.load(f)
                    tmp_out.unlink(missing_ok=True)
                else:
                    res = {
                        "dataset_size": int(d),
                        "n_nodes": int(n or 0),
                        "execution_time": 0.0,
                        "smiles_complexity": cfg.get("smiles_complexity", "medium"),
                        "status": "upload_only",
                        "job_id": "local",
                    }

                # sync_overhead_sec — local single-process run has no inter-node sync
                comp = float(timer._phase_times.get("computation_sec", 0.0))  # type: ignore[attr-defined]
                timer._phase_times["computation_sec"] = round(comp, 3)  # type: ignore[attr-defined]
                timer._phase_times["sync_overhead_sec"] = 0.0  # type: ignore[attr-defined]

                # result_upload_sec
                simulated_result_upload = random.uniform(1, 3)
                timer._phase_times["result_upload_sec"] = round(simulated_result_upload, 3)  # type: ignore[attr-defined]

            timings = timer.to_dict()

            result_row: Dict[str, Any] = {
                "experiment_id": cfg.get("name", "local_experiment"),
                "mode": mode,
                "dataset_size": int(d),
                "n_nodes": int(n or 0),
                "smiles_complexity": cfg.get("smiles_complexity", "medium"),
                "execution_time": float(res.get("execution_time", 0.0)),
                "status": res.get("status", "completed"),
                "job_id": res.get("job_id", "local"),
            }
            result_row.update(timings)

            results.append(result_row)

            # Stream to Google Sheets immediately after each local job
            if sheet_id:
                try:
                    append_timing_result(sheet_id, result_row)
                except Exception as exc:  # pragma: no cover - external service
                    logger.warning("Failed to append timing result to Sheets: {}", exc)

    results_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    # Save visualization panel for this local run.
    try:
        _save_experiment_plots(results, cfg, results_dir)
    except Exception as exc:  # pragma: no cover - best-effort plotting
        logger.warning("Failed to save visualization panel for local run: {}", exc)

    logger.success("Local experiment finished → {}", out_path)
    return out_path


def run_batch_experiment(config_path: Path, results_root: Path | None = None) -> Path:
    """
    Run experiment via AWS Batch for all (D, N) in the config.

    Assumes:
      - GOOGLE_SHEETS_ID is set for Sheets logging (Results tab)
      - S3_BUCKET (or AWS_S3_BUCKET), optional S3_PREFIX for dataset location
      - BATCH_JOB_QUEUE (or AWS_BATCH_JOB_QUEUE), BATCH_JOB_DEFINITION (or AWS_BATCH_JOB_DEFINITION)
      - Optional ``BATCH_ARRAY_TIMEOUT_SEC`` (default 14400): max seconds to wait for each
        array job's children (raise for overnight paper grids if jobs run longer than 4h wall).
      - Container reads env:
          DATASET_S3_BUCKET, DATASET_S3_PREFIX, DATASET_SIZE, N_NODES, SMILES_COMPLEXITY
        and uses AWS_BATCH_JOB_ARRAY_INDEX to select its shard.
    """
    cfg = load_config(config_path)
    mode = cfg.get("mode", "compute_only")
    if mode not in {"compute_only", "full_pipeline"}:
        raise SystemExit("Batch mode supports mode=compute_only or mode=full_pipeline")

    grid_pairs = _resolve_grid_pairs(cfg)
    complexity = cfg.get("smiles_complexity", "medium")
    descriptor_method = cfg.get("descriptor_method", "default")
    vcpus_per_node = cfg.get("vcpus_per_node", 4)
    gb_per_node = cfg.get("gb_per_node", 8)
    use_spot = bool(cfg.get("use_spot", False))
    n_replicas = max(1, int(cfg.get("n_replicas", 1)))

    s3_bucket = os.getenv("S3_BUCKET") or os.environ.get("AWS_S3_BUCKET")
    if not s3_bucket:
        raise SystemExit("Set S3_BUCKET or AWS_S3_BUCKET in environment")
    s3_prefix = os.getenv("S3_PREFIX", "chemoinformatics/")
    job_queue = resolve_batch_queue(use_spot=use_spot)
    job_def = os.getenv("BATCH_JOB_DEFINITION") or os.environ.get(
        "AWS_BATCH_JOB_DEFINITION"
    )
    if not job_def:
        raise SystemExit(
            "Set BATCH_JOB_DEFINITION or AWS_BATCH_JOB_DEFINITION in environment"
        )
    job_name_prefix = os.getenv("BATCH_JOB_NAME_PREFIX", "chemodesc")
    share_identifier = os.getenv("BATCH_SHARE_IDENTIFIER", "default")
    pricing_label = "SPOT" if use_spot else "ON-DEMAND"
    logger.info(
        "Batch experiment: pricing={}, n_replicas={}, queue={}, cells={}",
        pricing_label,
        n_replicas,
        job_queue,
        len(grid_pairs),
    )

    s3 = boto3.client("s3")
    batch = boto3.client("batch")

    results: List[Dict[str, Any]] = []
    results_dir = results_root or Path("experiments/results")
    out_path = results_dir / f"batch_{mode}_{_timestamp()}.json"

    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    array_timeout_sec = float(os.getenv("BATCH_ARRAY_TIMEOUT_SEC", str(4 * 3600)))

    csv_cache: dict[int, Any] = {}

    for d, n in tqdm(grid_pairs, desc="Grid cells", unit="cell"):
        local_csv = Path(f"datasets/samples/smiles_{d}_{complexity}.csv")
        if not local_csv.exists():
            raise FileNotFoundError(
                f"Expected dataset file not found: {local_csv}. "
                "Generate it first with the SMILES generator."
            )

        if d not in csv_cache:
            stats = _compute_dataset_stats(local_csv)
            import pandas as pd

            csv_cache[d] = pd.read_csv(local_csv)
        else:
            stats = _compute_dataset_stats(local_csv)

        df = csv_cache[d]

        if n <= 0:
            continue

        for replica_index in range(n_replicas):
                replica_suffix = (
                    f"_r{replica_index}" if n_replicas > 1 else ""
                )
                shards_prefix = f"{s3_prefix.rstrip('/')}/D{d}_N{n}{replica_suffix}"

                with ExperimentTimer() as s3_timer:
                    with s3_timer.phase("s3_upload_sec"):
                        with tempfile.TemporaryDirectory() as tmpdir:
                            tmpdir_path = Path(tmpdir)
                            # Always upload exactly N shards (indices 0..N-1).
                            # Ceil-split leaves trailing empty shards when D % N != 0;
                            # skipping them caused Batch children to 404 (N=128 @ D=5k).
                            num_rows = len(df)
                            rows_per_shard = (num_rows + n - 1) // n
                            for i in range(n):
                                start_idx = i * rows_per_shard
                                end_idx = min(num_rows, (i + 1) * rows_per_shard)
                                shard_df = df.iloc[start_idx:end_idx]
                                if shard_df.empty:
                                    shard_df = df.iloc[0:0].copy()
                                    if "smiles" not in shard_df.columns:
                                        import pandas as pd

                                        shard_df = pd.DataFrame(columns=["smiles"])
                                local_shard = tmpdir_path / f"shard_{i}.csv"
                                shard_df.to_csv(local_shard, index=False)
                                shard_key = f"{shards_prefix}/shard_{i}.csv"
                                s3.upload_file(str(local_shard), s3_bucket, shard_key)
                    s3_timings = s3_timer.to_dict()

                s3_upload_sec = s3_timings.get("s3_upload_sec", 0.0)
                job_name = f"{job_name_prefix}-D{d}-N{n}{replica_suffix}"
                batch_cfg = BatchJobConfig(
                    job_name=job_name,
                    job_queue=job_queue,
                    job_definition=job_def,
                    dataset_s3_bucket=s3_bucket,
                    dataset_s3_prefix=shards_prefix,
                    n_nodes=n,
                    dataset_size=d,
                    smiles_complexity=complexity,
                    descriptor_method=descriptor_method,
                    use_spot=use_spot,
                    share_identifier=share_identifier,
                    retry_attempts=int(os.getenv("BATCH_RETRY_ATTEMPTS", "2")),
                )
                submit_ts = time.time()
                parent_job_id = submit_batch_job(batch_cfg)
                logger.info(
                    "Submitted array Batch job {} (parent id={}, size={}, replica={}/{})",
                    job_name, parent_job_id, n, replica_index + 1, n_replicas,
                )
                running_deadline = os.getenv("BATCH_RUNNING_DEADLINE_SEC")
                child_jobs = _wait_for_array_job_cluster(
                    batch=batch, parent_job_id=parent_job_id,
                    expected_size=n, timeout_sec=array_timeout_sec,
                    submit_ts_sec=submit_ts,
                    running_deadline_sec=(
                        float(running_deadline) if running_deadline else None
                    ),
                )
                array_timings = derive_batch_array_timings(child_jobs, submit_ts_sec=submit_ts)
                shard_walls = _fetch_shard_wallclocks(
                    s3, bucket=s3_bucket, shards_prefix=shards_prefix, n_shards=n,
                )
                worker_computation_sec = max_shard_wallclock_sec(shard_walls)
                computation_sec = (
                    worker_computation_sec if worker_computation_sec is not None
                    else array_timings.computation_sec
                )
                if worker_computation_sec is not None:
                    logger.info(
                        "Using worker wallclock max {:.1f}s (AWS child max {:.1f}s)",
                        worker_computation_sec, array_timings.computation_sec,
                    )
                total_cost_usd = 0.0
                total_cost_spot_usd = 0.0
                total_cost_ondemand_usd = 0.0
                for j in child_jobs:
                    started_at = j.get("startedAt", 0)
                    stopped_at = j.get("stoppedAt", 0)
                    runtime_sec = (
                        (stopped_at - started_at) / 1000.0 if started_at and stopped_at else 0.0
                    )
                    container = j.get("container", {})
                    vcpus = float(container.get("vcpus", vcpus_per_node))
                    memory_mb = float(container.get("memory", gb_per_node * 1024))
                    memory_gb = memory_mb / 1024.0
                    spot_part = container_runtime_cost_usd(
                        vcpus, memory_gb, runtime_sec, tier=PricingTier.SPOT
                    )
                    od_part = container_runtime_cost_usd(
                        vcpus, memory_gb, runtime_sec, tier=PricingTier.ON_DEMAND
                    )
                    total_cost_spot_usd += spot_part
                    total_cost_ondemand_usd += od_part
                    tier = tier_from_use_spot(use_spot)
                    total_cost_usd += (
                        spot_part if tier == PricingTier.SPOT else od_part
                    )
                status_set = {j.get("status", "UNKNOWN") for j in child_jobs}
                if not status_set:
                    status = "UNKNOWN"
                elif status_set <= {"SUCCEEDED"}:
                    status = "SUCCEEDED"
                elif "FAILED" in status_set:
                    status = "FAILED"
                else:
                    status = ",".join(sorted(status_set))
                timer = ExperimentTimer()
                timer.set_metadata(
                    dataset_size_mb=stats["dataset_size_mb"],
                    smiles_avg_length=stats["smiles_avg_length"],
                    smiles_complexity=complexity,
                )
                timer._phase_times["s3_upload_sec"] = float(s3_upload_sec)  # type: ignore[attr-defined]
                timer._phase_times["cluster_init_sec"] = array_timings.cluster_init_sec  # type: ignore[attr-defined]
                timer._phase_times["scheduling_sec"] = array_timings.scheduling_sec  # type: ignore[attr-defined]
                timer._phase_times["computation_sec"] = computation_sec  # type: ignore[attr-defined]
                timer._phase_times["sync_overhead_sec"] = 0.0  # type: ignore[attr-defined]
                timer._phase_times["result_upload_sec"] = 0.0  # type: ignore[attr-defined]
                include_init = mode == "full_pipeline"
                total_pipeline = array_timings.total_pipeline_sec(
                    s3_upload_sec=float(s3_upload_sec), result_upload_sec=0.0,
                    include_cluster_init=include_init,
                )
                timer._phase_times["total_pipeline_sec"] = total_pipeline  # type: ignore[attr-defined]
                timings = timer.to_dict()
                wall_clock_sec = round(
                    float(s3_upload_sec) + float(array_timings.cluster_init_sec)
                    + float(array_timings.cluster_parallel_sec), 3,
                )
                base_notes = os.getenv("BATCH_RESULT_NOTES", "")
                replica_note = (
                    f"replica={replica_index + 1}/{n_replicas}" if n_replicas > 1 else ""
                )
                notes = "; ".join(x for x in (base_notes, replica_note) if x)
                result_row: Dict[str, Any] = {
                    "experiment_id": cfg.get("name", "batch_experiment"),
                    "mode": mode,
                    "dataset_size": int(d),
                    "n_nodes": int(n),
                    "replica_index": replica_index,
                    "n_replicas": n_replicas,
                    "use_spot": use_spot,
                    "smiles_complexity": complexity,
                    "execution_time": float(computation_sec),
                    "cluster_parallel_sec": float(array_timings.cluster_parallel_sec),
                    "wall_clock_sec": wall_clock_sec,
                    "n_children_started": array_timings.n_children_started,
                    "n_children_finished": array_timings.n_children_finished,
                    "status": status,
                    "job_id": parent_job_id,
                    "cost_usd": round(total_cost_usd, 4),
                    "cost_spot_usd": round(total_cost_spot_usd, 4),
                    "cost_ondemand_usd": round(total_cost_ondemand_usd, 4),
                    "pricing_tier": tier_label(use_spot),
                    "use_spot": use_spot,
                    "notes": notes,
                }
                result_row.update(timings)
                results.append(result_row)
                if sheet_id:
                    try:
                        append_timing_result(sheet_id, result_row)
                    except Exception as exc:
                        logger.warning("Failed to append timing result to Sheets: {}", exc)

    results_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    # Save visualization panel for this Batch run.
    try:
        _save_experiment_plots(results, cfg, results_dir)
    except Exception as exc:  # pragma: no cover - best-effort plotting
        logger.warning("Failed to save visualization panel for Batch run: {}", exc)

    logger.success("Batch experiment finished → {}", out_path)
    return out_path


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Run descriptor computation experiments."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=False,
        help="Path to experiment YAML config. If omitted, you must provide --dataset-sizes and --node-configs.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run in local mode (no AWS Batch).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["compute_only", "upload_only", "full_pipeline"],
        default=None,
        help="Override experiment mode (otherwise taken from config).",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="Directory containing smiles_{size}_{complexity}.csv files (default: datasets/samples).",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Optional experiment name when generating an ad-hoc config.",
    )
    parser.add_argument(
        "--smiles-complexity",
        type=str,
        choices=["low", "medium", "high"],
        default=None,
        help="Override SMILES complexity for ad-hoc configs.",
    )
    parser.add_argument(
        "--dataset-sizes",
        type=int,
        nargs="+",
        default=None,
        help="Dataset sizes D (e.g. --dataset-sizes 5000 10000) for ad-hoc configs.",
    )
    parser.add_argument(
        "--node-configs",
        type=int,
        nargs="+",
        default=None,
        help="Node counts N (e.g. --node-configs 25 50) for ad-hoc configs.",
    )
    parser.add_argument(
        "--vcpus-per-node",
        type=int,
        default=None,
        help="vCPUs per node for ad-hoc Batch configs (default: 4).",
    )
    parser.add_argument(
        "--gb-per-node",
        type=int,
        default=None,
        help="GB of memory per node for ad-hoc Batch configs (default: 8).",
    )
    parser.add_argument(
        "--use-spot",
        action="store_true",
        default=None,
        help="Use Spot Batch queue (ad-hoc configs only; default: false).",
    )
    parser.add_argument(
        "--n-replicas",
        type=int,
        default=None,
        help="Independent replicas per (D,N) cell (ad-hoc configs; default: 1).",
    )
    parser.add_argument(
        "--skip-pre-estimate",
        action="store_true",
        help="Skip writing experiments/results/<run>/estimation/estimate.json before the run.",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip writing verification_report.json after the run (when a pre-run estimate exists).",
    )
    args = parser.parse_args()

    skip_estimate = args.skip_pre_estimate or os.getenv("SKIP_PRE_RUN_ESTIMATE") == "1"

    # If no config file is provided, synthesize an ad-hoc config and store it
    # under a dedicated results subfolder alongside the JSON output.
    results_root: Path | None = None

    if args.config is not None:
        cfg_preview = load_config(args.config)
        run_id = _timestamp()
        exp_name = cfg_preview.get("name") or "experiment"
        results_root = Path("experiments/results") / f"{exp_name}_{run_id}"
        results_root.mkdir(parents=True, exist_ok=True)
        frozen_cfg = results_root / "config.yaml"
        shutil.copy2(args.config, frozen_cfg)
        config_path = frozen_cfg
        if not skip_estimate:
            _write_pre_run_estimate(frozen_cfg, results_root, args.dataset_dir)
    else:
        if not args.dataset_sizes or not args.node_configs:
            parser.error(
                "Either --config or both --dataset-sizes and --node-configs must be provided."
            )

        cfg: Dict[str, Any] = {
            "name": args.name or "ad_hoc_experiment",
            "mode": args.mode or "compute_only",
            "smiles_complexity": args.smiles_complexity or "medium",
            "descriptor_method": "default",
            "dataset_sizes": args.dataset_sizes,
            "node_configs": args.node_configs,
            "vcpus_per_node": args.vcpus_per_node or 4,
            "gb_per_node": args.gb_per_node or 8,
            "use_spot": bool(args.use_spot) if args.use_spot is not None else False,
            "n_replicas": max(1, int(args.n_replicas)) if args.n_replicas is not None else 1,
        }

        run_id = _timestamp()
        results_root = Path("experiments/results") / f"{cfg['name']}_{run_id}"
        results_root.mkdir(parents=True, exist_ok=True)
        config_path = results_root / "config.yaml"

        with open(config_path, "w") as f:
            yaml.safe_dump(cfg, f)

        if not skip_estimate:
            _write_pre_run_estimate(config_path, results_root, args.dataset_dir)

    if args.local:
        result_json = run_local_experiment(
            config_path,
            override_mode=args.mode,
            dataset_dir=args.dataset_dir,
            results_root=results_root,
        )
    else:
        result_json = run_batch_experiment(config_path, results_root=results_root)

    if (
        results_root is not None
        and not skip_estimate
        and not args.skip_verification
    ):
        _write_verification_report(results_root, result_json)


if __name__ == "__main__":
    main()

