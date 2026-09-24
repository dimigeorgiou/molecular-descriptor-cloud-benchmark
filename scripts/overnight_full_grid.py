#!/usr/bin/env python3
"""
Overnight full-grid orchestrator: CE scale-down → OD shape pass → Spot 10-rep data run.

See user task spec in repo chat / tmp/overnight_run.log header.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import yaml
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
LOG_PATH = REPO / "tmp" / "overnight_run.log"
REPORT_PATH = REPO / "tmp" / "overnight_run_report.md"
STATE_PATH = REPO / "tmp" / "overnight_run_state.json"

CE_SPOT = "chemo-ec2-worker"
CE_OD = "chemo-ec2-worker-ondemand"
SCALE_DOWN_MIN = 20

OD_EXPERIMENTS = ["overnight_od_shape_low", "overnight_od_shape_medium"]
SPOT_EXPERIMENTS = ["overnight_spot_data_low", "overnight_spot_data_medium"]

OD_CONFIGS = [
    REPO / "experiments/configs/overnight_od_shape_low.yaml",
    REPO / "experiments/configs/overnight_od_shape_medium.yaml",
]
SPOT_CONFIGS = [
    REPO / "experiments/configs/overnight_spot_data_low.yaml",
    REPO / "experiments/configs/overnight_spot_data_medium.yaml",
]

OD_COST_LIMIT = 5.0
SPOT_COST_LIMIT = 40.0
OD_BATCH_CELLS = 10
SPOT_BATCH_CELLS = 5  # 5 cells × 10 reps = 50 jobs per cost check


class StopRun(Exception):
    """Guardrail or fatal error — stop overnight run."""


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"[{_utc()}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


def grid_pairs_from_config(path: Path) -> list[tuple[int, int]]:
    sys.path.insert(0, str(REPO))
    from experiments.run_experiment import _resolve_grid_pairs

    return _resolve_grid_pairs(load_yaml(path))


def chunk_pairs(pairs: list[tuple[int, int]], size: int) -> list[list[tuple[int, int]]]:
    return [pairs[i : i + size] for i in range(0, len(pairs), size)]


def write_batch_config(base: Path, pairs: list[tuple[int, int]], out: Path) -> None:
    cfg = load_yaml(base)
    cfg["grid_pairs"] = [[d, n] for d, n in pairs]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def apply_scale_down_delays(region: str) -> None:
    log("STEP 1: Applying minScaleDownDelayMinutes=20 on Spot + On-Demand CEs")
    for ce in (CE_SPOT, CE_OD):
        subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/apply_ce_scale_down_delay.py"),
                "--ce",
                ce,
                "--minutes",
                str(SCALE_DOWN_MIN),
                "--region",
                region,
            ],
            check=True,
            cwd=str(REPO),
        )
    batch = boto3.client("batch", region_name=region)
    for _ in range(18):
        ok = True
        for ce in (CE_SPOT, CE_OD):
            env = batch.describe_compute_environments(computeEnvironments=[ce])[
                "computeEnvironments"
            ][0]
            sp = env.get("computeResources", {}).get("scalingPolicy") or {}
            delay = sp.get("minScaleDownDelayMinutes")
            status = env.get("status")
            update_status = env.get("updateStatus", "VALID")
            log(
                f"CE {ce}: status={status} updateStatus={update_status} "
                f"minScaleDownDelayMinutes={delay}"
            )
            if status != "VALID" or update_status not in ("VALID", None):
                ok = False
            if delay != SCALE_DOWN_MIN:
                ok = False
        if ok:
            log("STEP 1: CONFIRMED scale-down delay=20 on both CEs")
            return
        time.sleep(10)
    raise StopRun("CE scale-down delay not VALID after 3 minutes — aborting")


def verify_aws(region: str) -> None:
    try:
        sts = boto3.client("sts", region_name=region)
        sts.get_caller_identity()
    except Exception as exc:
        raise StopRun(f"AWS credentials invalid: {exc}") from exc
    batch = boto3.client("batch", region_name=region)
    for ce in (CE_SPOT, CE_OD):
        env = batch.describe_compute_environments(computeEnvironments=[ce])[
            "computeEnvironments"
        ][0]
        if env.get("status") != "VALID":
            raise StopRun(f"Compute environment {ce} status={env.get('status')}")


def sheets_rows(experiment_ids: list[str]) -> list[dict[str, Any]]:
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if not sheet_id:
        return []
    from src.monitoring.sheets import read_results_rows

    raw = read_results_rows(sheet_id)
    if not raw:
        return []
    hdr = {h: i for i, h in enumerate(raw[0])}

    def col(row: list[str], name: str) -> str:
        i = hdr.get(name)
        return row[i] if i is not None and i < len(row) else ""

    rows: list[dict[str, Any]] = []
    for row in raw[1:]:
        exp = col(row, "Experiment ID")
        if exp not in experiment_ids:
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
                "status": col(row, "Status"),
                "cost_usd": float(col(row, "Cost (USD)") or 0),
                "wall_clock_sec": float(col(row, "Wall Clock (s)") or 0),
                "cluster_init_sec": float(col(row, "Cluster Init (s)") or 0),
                "replica_index": replica_index,
                "notes": notes,
            }
        )
    return rows


def sheets_cost(experiment_ids: list[str]) -> float:
    return round(sum(r["cost_usd"] for r in sheets_rows(experiment_ids)), 4)


def count_statuses(experiment_ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in sheets_rows(experiment_ids):
        st = r["status"] or "UNKNOWN"
        counts[st] += 1
    return dict(counts)


class Heartbeat:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(900):  # 15 min
            exp_ids = self.state.get("active_experiment_ids", [])
            counts = count_statuses(exp_ids) if exp_ids else {}
            log(
                f"HEARTBEAT step={self.state.get('step')} "
                f"submitted={self.state.get('jobs_submitted', 0)} "
                f"succeeded={counts.get('SUCCEEDED', 0)} "
                f"failed={counts.get('FAILED', 0)} "
                f"timeout={counts.get('TIMEOUT', 0)} "
                f"cost_usd={self.state.get('cumulative_cost_usd', 0):.4f}"
            )
            save_state(self.state)


def run_experiment_subprocess(config_path: Path) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env.setdefault("BATCH_RUNNING_DEADLINE_SEC", "900")
    env.setdefault("BATCH_ARRAY_TIMEOUT_SEC", "7200")
    env["SKIP_PRE_RUN_ESTIMATE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "experiments/run_experiment.py"),
            "--config",
            str(config_path),
            "--skip-pre-estimate",
            "--skip-verification",
        ],
        cwd=str(REPO),
        env=env,
    )
    return proc.returncode


def check_all_replicas_failed(
    experiment_id: str, pairs: list[tuple[int, int]], n_replicas: int
) -> list[tuple[int, int]]:
    rows = [r for r in sheets_rows([experiment_id]) if r["experiment_id"] == experiment_id]
    bad: list[tuple[int, int]] = []
    for d, n in pairs:
        cell_rows = [r for r in rows if r["dataset_size"] == d and r["n_nodes"] == n]
        if len(cell_rows) < n_replicas:
            continue
        statuses = {r["status"] for r in cell_rows}
        if statuses <= {"FAILED", "TIMEOUT"}:
            bad.append((d, n))
    return bad


def run_batched_pass(
    *,
    step: str,
    base_configs: list[Path],
    batch_cells: int,
    cost_limit: float,
    state: dict[str, Any],
    stop_on_all_replicas_failed: bool,
    n_replicas: int,
) -> None:
    exp_ids = [load_yaml(p)["name"] for p in base_configs]
    state["step"] = step
    state["active_experiment_ids"] = exp_ids
    save_state(state)

    batch_dir = REPO / "tmp" / "overnight_batches" / step
    batch_dir.mkdir(parents=True, exist_ok=True)

    for base_cfg in base_configs:
        name = load_yaml(base_cfg)["name"]
        pairs = grid_pairs_from_config(base_cfg)
        chunks = chunk_pairs(pairs, batch_cells)
        log(f"{step}: {name} — {len(pairs)} cells in {len(chunks)} batches")
        for bi, chunk in enumerate(chunks):
            batch_cfg = batch_dir / f"{name}_batch{bi:02d}.yaml"
            write_batch_config(base_cfg, chunk, batch_cfg)
            jobs_in_batch = len(chunk) * n_replicas
            state["jobs_submitted"] = state.get("jobs_submitted", 0) + jobs_in_batch
            log(f"{step}: running {batch_cfg.name} ({len(chunk)} cells, {jobs_in_batch} jobs)")
            rc = run_experiment_subprocess(batch_cfg)
            if rc != 0:
                log(f"WARN: batch {batch_cfg.name} exit code {rc} — continuing")

            state["cumulative_cost_usd"] = sheets_cost(exp_ids)
            save_state(state)
            log(
                f"{step}: post-batch cost=${state['cumulative_cost_usd']:.4f} "
                f"(limit=${cost_limit:.2f})"
            )
            if state["cumulative_cost_usd"] > cost_limit:
                raise StopRun(
                    f"cumulative cost ${state['cumulative_cost_usd']:.2f} "
                    f"exceeded limit ${cost_limit:.2f} in {step}"
                )

            if stop_on_all_replicas_failed:
                bad = check_all_replicas_failed(name, chunk, n_replicas)
                if bad:
                    raise StopRun(
                        f"Spot cell(s) failed all {n_replicas} replicas: {bad} — stopping"
                    )


def coefficient_of_variation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = statistics.mean(values)
    if m <= 0:
        return 0.0
    return float(statistics.stdev(values) / m)


def generate_morning_report(state: dict[str, Any], stopped_reason: str | None) -> None:
    od_rows = sheets_rows(OD_EXPERIMENTS)
    spot_rows = sheets_rows(SPOT_EXPERIMENTS)

    def tally(rows: list[dict[str, Any]]) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for r in rows:
            c[r["status"] or "UNKNOWN"] += 1
        return dict(c)

    od_tally = tally(od_rows)
    spot_tally = tally(spot_rows)
    od_cost = round(sum(r["cost_usd"] for r in od_rows), 4)
    spot_cost = round(sum(r["cost_usd"] for r in spot_rows), 4)

    # Cell failures
    def cell_failures(rows: list[dict[str, Any]], tier: str) -> list[dict[str, Any]]:
        by_cell: dict[tuple[int, int, str], list[str]] = defaultdict(list)
        for r in rows:
            key = (r["dataset_size"], r["n_nodes"], r["experiment_id"])
            by_cell[key].append(r["status"])
        out = []
        for (d, n, exp), statuses in sorted(by_cell.items()):
            fails = sum(1 for s in statuses if s not in ("SUCCEEDED", "completed"))
            if fails:
                out.append(
                    {
                        "tier": tier,
                        "experiment_id": exp,
                        "D": d,
                        "N": n,
                        "failures": fails,
                        "total": len(statuses),
                        "all_failed": fails == len(statuses),
                    }
                )
        return out

    failures = cell_failures(od_rows, "On-Demand") + cell_failures(spot_rows, "Spot")
    all_spot_dead = [f for f in failures if f["tier"] == "Spot" and f["all_failed"]]

    # Init CV per tier
    od_inits = [r["cluster_init_sec"] for r in od_rows if r["cluster_init_sec"] > 0]
    spot_inits = [r["cluster_init_sec"] for r in spot_rows if r["cluster_init_sec"] > 0]

    # Median wall_clock per D (Spot only, SUCCEEDED)
    by_d: dict[int, list[float]] = defaultdict(list)
    for r in spot_rows:
        if r["status"] == "SUCCEEDED" and r["wall_clock_sec"] > 0:
            by_d[r["dataset_size"]].append(r["wall_clock_sec"])
    median_table = {
        str(d): round(statistics.median(v), 2) for d, v in sorted(by_d.items())
    }

    # N>=150 failure rate
    def fail_rate(rows: list[dict[str, Any]], high_n: bool) -> tuple[int, int]:
        subset = [r for r in rows if (r["n_nodes"] >= 150) == high_n]
        if not subset:
            return 0, 0
        fails = sum(1 for r in subset if r["status"] not in ("SUCCEEDED", "completed"))
        return fails, len(subset)

    spot_lo_f, spot_lo_t = fail_rate(spot_rows, False)
    spot_hi_f, spot_hi_t = fail_rate(spot_rows, True)
    n150_different = "yes" if spot_hi_t and spot_lo_t else "insufficient data"
    if spot_hi_t and spot_lo_t:
        hi_rate = spot_hi_f / spot_hi_t
        lo_rate = spot_lo_f / spot_lo_t
        n150_different = "yes" if hi_rate > lo_rate * 1.5 else "no"

    lines = [
        "# Overnight Full-Grid Run Report",
        "",
        f"Generated: {_utc()}",
        f"Stopped reason: {stopped_reason or 'completed'}",
        "",
        "## 1. Job counts",
        "",
        f"| Pass | SUCCEEDED | FAILED | TIMEOUT | other |",
        f"|------|-----------|--------|---------|-------|",
        f"| On-Demand shape | {od_tally.get('SUCCEEDED', 0)} | "
        f"{od_tally.get('FAILED', 0)} | {od_tally.get('TIMEOUT', 0)} | "
        f"{sum(v for k, v in od_tally.items() if k not in ('SUCCEEDED', 'FAILED', 'TIMEOUT'))} |",
        f"| Spot data | {spot_tally.get('SUCCEEDED', 0)} | "
        f"{spot_tally.get('FAILED', 0)} | {spot_tally.get('TIMEOUT', 0)} | "
        f"{sum(v for k, v in spot_tally.items() if k not in ('SUCCEEDED', 'FAILED', 'TIMEOUT'))} |",
        "",
        "## 2. Actual cost (Sheets `cost_usd`)",
        "",
        f"- On-Demand pass: **${od_cost}** (guardrail $5)",
        f"- Spot pass: **${spot_cost}** (guardrail $40)",
        f"- **Total: ${od_cost + spot_cost}**",
        "",
        "## 3. Cell-level failures",
        "",
    ]
    if not failures:
        lines.append("No failures recorded.")
    else:
        lines.append("| Tier | D | N | failures/total | all failed? |")
        lines.append("|------|---|---|----------------|-------------|")
        for f in failures:
            lines.append(
                f"| {f['tier']} | {f['D']} | {f['N']} | "
                f"{f['failures']}/{f['total']} | {f['all_failed']} |"
            )
    if all_spot_dead:
        lines.extend(["", "**FLAG: Spot cells with ALL replicas failed:**", ""])
        for f in all_spot_dead:
            lines.append(f"- D={f['D']} N={f['N']} ({f['experiment_id']})")

    lines.extend(
        [
            "",
            "## 4. Init CV (tonight's data)",
            "",
            f"- On-Demand: CV={coefficient_of_variation(od_inits):.4f} "
            f"(n={len(od_inits)}, mean={statistics.mean(od_inits) if od_inits else 0:.1f}s)",
            f"- Spot: CV={coefficient_of_variation(spot_inits):.4f} "
            f"(n={len(spot_inits)}, mean={statistics.mean(spot_inits) if spot_inits else 0:.1f}s)",
            "",
            "## 5. Median wall_clock per D (Spot, SUCCEEDED)",
            "",
            "```json",
            json.dumps(median_table, indent=2),
            "```",
            "",
            "## 6. N≥150 Spot failure rate vs N<150",
            "",
        ]
    )
    if spot_lo_t:
        lines.append(
            f"- N<150: {spot_lo_f}/{spot_lo_t} failed "
            f"({100 * spot_lo_f / spot_lo_t:.1f}%)"
        )
    else:
        lines.append("- N<150: no data")
    if spot_hi_t:
        lines.append(
            f"- N≥150: {spot_hi_f}/{spot_hi_t} failed "
            f"({100 * spot_hi_f / spot_hi_t:.1f}%)"
        )
    else:
        lines.append("- N≥150: no data")
    lines.append(f"- Meaningfully higher at N≥150: **{n150_different}**")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Cost figures are empirical Sheets `cost_usd`, not `experiment_estimator.py`.",
            "- No model refit performed (non-goal).",
            "- OD pass is shape-check only; use Spot medians for replication data.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    log(f"Morning report → {REPORT_PATH}")


def main() -> int:
    load_dotenv(REPO / ".env")
    os.chdir(REPO)
    sys.path.insert(0, str(REPO))

    region = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
    LOG_PATH.write_text(f"=== OVERNIGHT FULL GRID START {_utc()} ===\n")

    state: dict[str, Any] = {
        "started_at": _utc(),
        "step": "init",
        "jobs_submitted": 0,
        "cumulative_cost_usd": 0.0,
        "active_experiment_ids": [],
    }
    save_state(state)

    hb = Heartbeat(state)
    hb.start()
    stopped_reason: str | None = None

    try:
        verify_aws(region)
        apply_scale_down_delays(region)

        log("STEP 2: On-Demand shape pass (1 rep × 84 cells)")
        run_batched_pass(
            step="2_od_shape",
            base_configs=OD_CONFIGS,
            batch_cells=OD_BATCH_CELLS,
            cost_limit=OD_COST_LIMIT,
            state=state,
            stop_on_all_replicas_failed=False,
            n_replicas=1,
        )

        log("STEP 3: Spot data run (10 reps × 84 cells)")
        run_batched_pass(
            step="3_spot_data",
            base_configs=SPOT_CONFIGS,
            batch_cells=SPOT_BATCH_CELLS,
            cost_limit=SPOT_COST_LIMIT,
            state=state,
            stop_on_all_replicas_failed=True,
            n_replicas=10,
        )
        log("OVERNIGHT RUN COMPLETED SUCCESSFULLY")
    except StopRun as exc:
        stopped_reason = str(exc)
        log(f"STOPPED: {stopped_reason}")
    except Exception as exc:
        stopped_reason = f"unexpected error: {exc}"
        log(f"STOPPED: {stopped_reason}")
        raise
    finally:
        hb.stop()
        generate_morning_report(state, stopped_reason)
        save_state(state)

    return 0 if stopped_reason is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
