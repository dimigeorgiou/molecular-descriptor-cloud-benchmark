#!/usr/bin/env python3
"""
Resume overnight grid after partial stop.

Phase A — Spot 10-rep: remaining cells with N<=125 (skip complete cells in Sheets).
Phase B — On-Demand 10-rep: all D × N∈{150,185} for low + medium (high-N data pass).
"""
from __future__ import annotations

import json
import os
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
REPORT_PATH = REPO / "tmp" / "overnight_resume_report.md"
STATE_PATH = REPO / "tmp" / "overnight_resume_state.json"

SPOT_BASE = {
    "low": REPO / "experiments/configs/overnight_spot_data_low.yaml",
    "medium": REPO / "experiments/configs/overnight_spot_data_medium.yaml",
}
OD_HIGHN_BASE = {
    "low": REPO / "experiments/configs/overnight_od_data_low_highn.yaml",
    "medium": REPO / "experiments/configs/overnight_od_data_medium_highn.yaml",
}

SPOT_EXP = ["overnight_spot_data_low", "overnight_spot_data_medium"]
OD_EXP = ["overnight_od_data_low_highn", "overnight_od_data_medium_highn"]

SPOT_N_MAX = 125
N_REPLICAS_SPOT = 10
N_REPLICAS_OD = 10
SPOT_BATCH = 5
OD_BATCH = 4
SPOT_COST_LIMIT = 38.0  # headroom under $40 total Spot budget
OD_COST_LIMIT = 15.0


class StopRun(Exception):
    pass


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"[{_utc()}] RESUME: {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


def grid_pairs(path: Path) -> list[tuple[int, int]]:
    sys.path.insert(0, str(REPO))
    from experiments.run_experiment import _resolve_grid_pairs

    return _resolve_grid_pairs(load_yaml(path))


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

    out: list[dict[str, Any]] = []
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
        out.append(
            {
                "experiment_id": exp,
                "dataset_size": int(col(row, "Dataset Size (D)") or 0),
                "n_nodes": int(col(row, "Nodes (N)") or 0),
                "status": col(row, "Status"),
                "cost_usd": float(col(row, "Cost (USD)") or 0),
                "replica_index": replica_index,
            }
        )
    return out


def succeeded_replicas(rows: list[dict], exp_id: str, d: int, n: int) -> int:
    return sum(
        1
        for r in rows
        if r["experiment_id"] == exp_id
        and r["dataset_size"] == d
        and r["n_nodes"] == n
        and r["status"] == "SUCCEEDED"
    )


def total_cost(rows: list[dict], exp_ids: list[str]) -> float:
    return round(
        sum(r["cost_usd"] for r in rows if r["experiment_id"] in exp_ids),
        4,
    )


def remaining_spot_pairs(complexity: str, rows: list[dict]) -> list[tuple[int, int]]:
    exp_id = f"overnight_spot_data_{complexity}"
    all_pairs = [
        (d, n) for d, n in grid_pairs(SPOT_BASE[complexity]) if n <= SPOT_N_MAX
    ]
    need: list[tuple[int, int]] = []
    for d, n in all_pairs:
        if succeeded_replicas(rows, exp_id, d, n) < N_REPLICAS_SPOT:
            need.append((d, n))
    return need


def remaining_od_highn_pairs(complexity: str, rows: list[dict]) -> list[tuple[int, int]]:
    exp_id = f"overnight_od_data_{complexity}_highn"
    all_pairs = grid_pairs(OD_HIGHN_BASE[complexity])
    need: list[tuple[int, int]] = []
    for d, n in all_pairs:
        if succeeded_replicas(rows, exp_id, d, n) < N_REPLICAS_OD:
            need.append((d, n))
    return need


def write_batch(base: Path, pairs: list[tuple[int, int]], out: Path) -> None:
    cfg = load_yaml(base)
    cfg["grid_pairs"] = [[d, n] for d, n in pairs]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def run_batch(config_path: Path) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env.setdefault("BATCH_RUNNING_DEADLINE_SEC", "900")
    env.setdefault("BATCH_ARRAY_TIMEOUT_SEC", "7200")
    env["SKIP_PRE_RUN_ESTIMATE"] = "1"
    return subprocess.run(
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
    ).returncode


def check_all_failed(
    exp_id: str, pairs: list[tuple[int, int]], n_replicas: int, rows: list[dict]
) -> list[tuple[int, int]]:
    bad: list[tuple[int, int]] = []
    for d, n in pairs:
        cell = [
            r
            for r in rows
            if r["experiment_id"] == exp_id
            and r["dataset_size"] == d
            and r["n_nodes"] == n
        ]
        if len(cell) < n_replicas:
            continue
        if all(r["status"] != "SUCCEEDED" for r in cell):
            bad.append((d, n))
    return bad


def verify_ce(region: str) -> None:
    batch = boto3.client("batch", region_name=region)
    for ce in ("chemo-ec2-worker", "chemo-ec2-worker-ondemand"):
        env = batch.describe_compute_environments(computeEnvironments=[ce])[
            "computeEnvironments"
        ][0]
        delay = (env.get("computeResources", {}).get("scalingPolicy") or {}).get(
            "minScaleDownDelayMinutes"
        )
        if env.get("status") != "VALID" or delay != 20:
            raise StopRun(f"CE {ce} not ready (status={env.get('status')} delay={delay})")
    log("CE check OK (both VALID, delay=20)")


def run_phase(
    *,
    phase: str,
    items: list[tuple[str, Path, list[tuple[int, int]]]],
    batch_size: int,
    n_replicas: int,
    cost_limit: float,
    exp_ids: list[str],
    state: dict[str, Any],
    stop_on_all_failed: bool,
) -> None:
    batch_dir = REPO / "tmp" / "overnight_resume_batches" / phase
    batch_dir.mkdir(parents=True, exist_ok=True)
    state["step"] = phase
    state["active_experiment_ids"] = exp_ids
    save_state(state)

    for label, base_cfg, pairs in items:
        if not pairs:
            log(f"{phase}: {label} — nothing remaining, skip")
            continue
        chunks = [pairs[i : i + batch_size] for i in range(0, len(pairs), batch_size)]
        log(f"{phase}: {label} — {len(pairs)} cells in {len(chunks)} batches")
        exp_id = load_yaml(base_cfg)["name"]
        for i, chunk in enumerate(chunks):
            out = batch_dir / f"{label}_batch{i:02d}.yaml"
            write_batch(base_cfg, chunk, out)
            jobs = len(chunk) * n_replicas
            state["jobs_submitted"] = state.get("jobs_submitted", 0) + jobs
            log(f"{phase}: running {out.name} ({len(chunk)} cells)")
            rc = run_batch(out)
            if rc != 0:
                log(f"WARN: {out.name} exit {rc}")

            rows = sheets_rows(exp_ids)
            phase_cost = total_cost(rows, exp_ids)
            state["cumulative_cost_usd"] = phase_cost
            save_state(state)
            log(f"{phase}: cost=${phase_cost:.4f} (limit=${cost_limit:.2f})")
            if phase_cost > cost_limit:
                raise StopRun(f"{phase} cost ${phase_cost:.2f} > ${cost_limit:.2f}")

            if stop_on_all_failed:
                rows = sheets_rows([exp_id])
                bad = check_all_failed(exp_id, chunk, n_replicas, rows)
                if bad:
                    raise StopRun(f"{phase} all replicas failed at cells {bad}")


class Heartbeat:
    def __init__(self, state: dict[str, Any], exp_ids: list[str]) -> None:
        self.state = state
        self.exp_ids = exp_ids
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(900):
            rows = sheets_rows(self.exp_ids)
            ok = sum(1 for r in rows if r["status"] == "SUCCEEDED")
            fail = sum(1 for r in rows if r["status"] not in ("SUCCEEDED", "completed"))
            log(
                f"HEARTBEAT step={self.state.get('step')} "
                f"submitted={self.state.get('jobs_submitted', 0)} "
                f"succeeded={ok} failed={fail} cost=${self.state.get('cumulative_cost_usd', 0):.4f}"
            )


def write_report(state: dict[str, Any], reason: str | None) -> None:
    rows = sheets_rows(SPOT_EXP + OD_EXP)
    spot_ok = sum(
        1 for r in rows if r["experiment_id"] in SPOT_EXP and r["status"] == "SUCCEEDED"
    )
    od_ok = sum(
        1 for r in rows if r["experiment_id"] in OD_EXP and r["status"] == "SUCCEEDED"
    )
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Overnight Resume Report",
                "",
                f"Generated: {_utc()}",
                f"Outcome: {reason or 'completed'}",
                "",
                f"- Spot succeeded rows: {spot_ok}",
                f"- OD high-N succeeded rows: {od_ok}",
                f"- Resume cost (these exp ids): ${total_cost(rows, SPOT_EXP + OD_EXP):.4f}",
                f"- Jobs submitted this resume: {state.get('jobs_submitted', 0)}",
                "",
                "See `tmp/overnight_run.log` for full timeline.",
            ]
        )
        + "\n"
    )
    log(f"Resume report → {REPORT_PATH}")


def main() -> int:
    load_dotenv(REPO / ".env")
    os.chdir(REPO)
    sys.path.insert(0, str(REPO))

    region = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
    log("=== RESUME START ===")

    all_exp = SPOT_EXP + OD_EXP
    rows = sheets_rows(all_exp)

    spot_items = [
        ("spot_low", SPOT_BASE["low"], remaining_spot_pairs("low", rows)),
        ("spot_medium", SPOT_BASE["medium"], remaining_spot_pairs("medium", rows)),
    ]
    od_items = [
        ("od_low_highn", OD_HIGHN_BASE["low"], remaining_od_highn_pairs("low", rows)),
        (
            "od_medium_highn",
            OD_HIGHN_BASE["medium"],
            remaining_od_highn_pairs("medium", rows),
        ),
    ]

    for label, _, pairs in spot_items + od_items:
        log(f"plan {label}: {len(pairs)} cells to run")

    state: dict[str, Any] = {
        "started_at": _utc(),
        "step": "init",
        "jobs_submitted": 0,
        "cumulative_cost_usd": 0.0,
    }
    save_state(state)
    hb = Heartbeat(state, all_exp)
    hb.start()
    reason: str | None = None

    try:
        boto3.client("sts", region_name=region).get_caller_identity()
        verify_ce(region)

        log("PHASE A: Spot 10-rep (N<=125, skip complete cells)")
        run_phase(
            phase="A_spot",
            items=spot_items,
            batch_size=SPOT_BATCH,
            n_replicas=N_REPLICAS_SPOT,
            cost_limit=SPOT_COST_LIMIT,
            exp_ids=SPOT_EXP,
            state=state,
            stop_on_all_failed=True,
        )

        log("PHASE B: On-Demand 10-rep high-N (N=150,185)")
        run_phase(
            phase="B_od_highn",
            items=od_items,
            batch_size=OD_BATCH,
            n_replicas=N_REPLICAS_OD,
            cost_limit=OD_COST_LIMIT,
            exp_ids=OD_EXP,
            state=state,
            stop_on_all_failed=False,  # expect some OD high-N flakes; log not halt
        )
        log("RESUME COMPLETED")
    except StopRun as exc:
        reason = str(exc)
        log(f"STOPPED: {reason}")
    except Exception as exc:
        reason = f"error: {exc}"
        log(f"STOPPED: {reason}")
        raise
    finally:
        hb.stop()
        write_report(state, reason)
        save_state(state)

    return 0 if reason is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
