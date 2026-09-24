#!/usr/bin/env python3
"""
Run micro-grid low-N sensitivity study (D=5k/10k, N=1..25, 5 replicas).

Spot + On-Demand × low + medium → 4 configs, ~200 array jobs total.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
LOG_PATH = REPO / "tmp" / "micro_grid_low_n.log"
STATE_PATH = REPO / "tmp" / "micro_grid_low_n_state.json"
REPORT_PATH = REPO / "tmp" / "micro_grid_low_n_report.md"

ALL_CONFIGS = [
    REPO / "experiments/configs/micro_grid_low_n_low_spot.yaml",
    REPO / "experiments/configs/micro_grid_low_n_low_ondemand.yaml",
    REPO / "experiments/configs/micro_grid_low_n_medium_spot.yaml",
    REPO / "experiments/configs/micro_grid_low_n_medium_ondemand.yaml",
]
COST_LIMIT_USD = 18.0
PARTIAL_COST_LIMIT_USD = 10.0


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"[{_utc()}] MICRO_LOW_N: {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def run_config(path: Path) -> int:
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
            str(path),
            "--skip-pre-estimate",
            "--skip-verification",
        ],
        cwd=str(REPO),
        env=env,
    ).returncode


def sheet_cost(exp_ids: list[str]) -> float:
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if not sheet_id:
        return 0.0
    from src.monitoring.sheets import read_results_rows

    rows = read_results_rows(sheet_id)
    if not rows:
        return 0.0
    hdr = {h: i for i, h in enumerate(rows[0])}
    exp_i = hdr.get("Experiment ID", 0)
    cost_i = hdr.get("Cost (USD)")
    total = 0.0
    for row in rows[1:]:
        if row[exp_i] not in exp_ids:
            continue
        if cost_i is not None and cost_i < len(row) and row[cost_i]:
            total += float(row[cost_i])
    return round(total, 4)


def resolve_configs(argv: list[str]) -> tuple[list[Path], float]:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        action="append",
        dest="configs",
        metavar="NAME_OR_PATH",
        help="Config file name under experiments/configs/ or path (repeatable)",
    )
    args = parser.parse_args(argv)
    if not args.configs:
        return ALL_CONFIGS, COST_LIMIT_USD
    resolved: list[Path] = []
    for item in args.configs:
        p = Path(item)
        if p.is_absolute():
            pass
        elif p.suffix and (REPO / "experiments/configs" / p.name).exists():
            p = REPO / "experiments/configs" / p.name
        elif not p.suffix:
            p = REPO / "experiments/configs" / f"{item}.yaml"
        else:
            p = REPO / p
        if not p.exists():
            raise SystemExit(f"Config not found: {p}")
        resolved.append(p)
    limit = PARTIAL_COST_LIMIT_USD if len(resolved) < len(ALL_CONFIGS) else COST_LIMIT_USD
    return resolved, limit


def main() -> int:
    load_dotenv(REPO / ".env")
    os.chdir(REPO)
    sys.path.insert(0, str(REPO))

    configs, cost_limit = resolve_configs(sys.argv[1:])

    exp_ids = []
    for cfg_path in configs:
        with cfg_path.open() as f:
            exp_ids.append(yaml.safe_load(f)["name"])

    state = {
        "started_at": _utc(),
        "status": "running",
        "configs": [p.name for p in configs],
        "n_replicas": 5,
        "grid": "D=5000,10000 × N=1,5,10,15,25",
        "cost_limit_usd": cost_limit,
    }
    save_state(state)
    log("=== MICRO LOW-N START ===")
    log(
        f"plan: {len(configs)} config(s) × 10 cells × 5 replicas → "
        f"~{len(configs) * 50} array jobs (cost limit ${cost_limit:.0f})"
    )

    reason: str | None = None
    try:
        for cfg_path in configs:
            with cfg_path.open() as f:
                meta = yaml.safe_load(f)
            tier = "SPOT" if meta.get("use_spot") else "ON-DEMAND"
            log(f"running {cfg_path.name} [{tier}]")
            state["current_config"] = cfg_path.name
            state["status"] = "running"
            save_state(state)
            rc = run_config(cfg_path)
            if rc != 0:
                log(f"WARN: {cfg_path.name} exit code {rc}")
            cost = sheet_cost(exp_ids)
            state["cumulative_cost_usd"] = cost
            save_state(state)
            log(f"cost so far=${cost:.4f} (limit=${cost_limit:.2f})")
            if cost > cost_limit:
                reason = f"cost ${cost:.2f} > ${cost_limit:.2f}"
                break
        if reason is None:
            log("MICRO LOW-N COMPLETED")
            state["status"] = "completed"
        else:
            log(f"STOPPED: {reason}")
            state["status"] = "stopped"
    except Exception as exc:
        reason = str(exc)
        state["status"] = "error"
        log(f"ERROR: {exc}")
        raise
    finally:
        state["finished_at"] = _utc()
        state["outcome"] = reason or "completed"
        save_state(state)
        REPORT_PATH.write_text(
            "\n".join(
                [
                    "# Micro-grid low-N report",
                    "",
                    f"Generated: {_utc()}",
                    f"Outcome: {state.get('outcome')}",
                    f"Cost (exp ids): ${state.get('cumulative_cost_usd', 0):.4f}",
                    "",
                    "Configs: low/medium × Spot/On-Demand",
                    "Grid: D=5000,10000 × N=1,5,10,15,25 × 5 replicas",
                    "",
                    f"Log: `{LOG_PATH.relative_to(REPO)}`",
                ]
            )
            + "\n"
        )
        log(f"Report → {REPORT_PATH}")

    return 0 if reason is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
