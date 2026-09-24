#!/usr/bin/env python3
"""
Paper 2 approved Scope: established-grid core top-up only.

+31 full_pipeline Spot jobs to bring N∈{25,50,75,100,125,150,185} × D∈{5..50}k
cells from 2 → 3 replicates. No Scope A/B. No CE bump.

Usage:
  PYTHONPATH=. python scripts/run_paper2_core_topup.py
  PYTHONPATH=. python scripts/run_paper2_core_topup.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CFG_DIR = REPO / "experiments/configs/paper2/core_topup"
LOGROOT = REPO / "tmp/paper2_rebuild/core_topup"
STATE = LOGROOT / "orchestrator_state.json"
PY = os.environ.get("PY", "/opt/anaconda3/envs/venv_chemoinformatics/bin/python")

CORE_N = (25, 50, 75, 100, 125, 150, 185)
CORE_D = (5000, 10000, 20000, 30000, 40000, 50000)


def _load_dotenv() -> None:
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cells_needing_topup() -> list[dict]:
    """Recompute from corrected sheet (or live if --refresh later)."""
    csv_path = REPO / "tmp/paper2_rebuild/corrected_sheet_succeeded.csv"
    rows = list(csv.DictReader(csv_path.open()))
    counts: dict[tuple, int] = defaultdict(int)
    for r in rows:
        if r.get("ModeNorm") != "full_pipeline":
            continue
        if r.get("Complexity") not in ("low", "medium"):
            continue
        try:
            D, N = int(r["D"]), int(r["N"])
        except Exception:
            continue
        if D not in CORE_D or N not in CORE_N:
            continue
        counts[(r["Complexity"], D, N)] += 1

    need = []
    for cx in ("low", "medium"):
        for D in CORE_D:
            for N in CORE_N:
                have = counts.get((cx, D, N), 0)
                gap = max(0, 3 - have)
                if gap:
                    name = f"paper2_core_topup_{cx}_d{D}_n{N}_rep{have + 1}"
                    need.append(
                        {
                            "name": name,
                            "cx": cx,
                            "D": D,
                            "N": N,
                            "have": have,
                            "need": gap,
                        }
                    )
    return need


def write_configs(cells: list[dict]) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    for c in cells:
        # one job per missing replicate (gap is always 1 for this campaign)
        for k in range(c["need"]):
            name = c["name"] if c["need"] == 1 else f"{c['name']}_k{k+1}"
            body = {
                "name": name,
                "mode": "full_pipeline",
                "smiles_complexity": c["cx"],
                "descriptor_method": "default",
                "dataset_sizes": [c["D"]],
                "node_configs": [c["N"]],
                "vcpus_per_node": 4,
                "gb_per_node": 8,
                "use_spot": True,
                "n_replicas": 1,
                "dataset_dir": "datasets/samples",
            }
            (CFG_DIR / f"{name}.yaml").write_text(yaml.safe_dump(body, sort_keys=False))


def _load_state() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text())
    return {"completed": [], "failed": [], "started_at": None, "job_ids": {}}


def _save_state(state: dict) -> None:
    LOGROOT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def run_one(name: str, timeout_sec: int) -> int:
    cfg = CFG_DIR / f"{name}.yaml"
    log = LOGROOT / f"{name}.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["SKIP_PRE_RUN_ESTIMATE"] = "1"
    env.setdefault("BATCH_RUNNING_DEADLINE_SEC", "1800")
    env.setdefault("SHEETS_UPDATE_COMPLEXITY", "0")
    env.setdefault("SHEETS_APPEND_ONLY", "1")
    cmd = [PY, str(REPO / "experiments/run_experiment.py"), "--config", str(cfg)]
    print(
        f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] RUN {name}",
        flush=True,
    )
    with log.open("a") as lf:
        lf.write(f"\n=== START {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n")
        lf.flush()
        proc = subprocess.Popen(
            cmd, cwd=str(REPO), env=env, stdout=lf, stderr=subprocess.STDOUT
        )
        try:
            return proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
            lf.write(f"\n=== TIMEOUT after {timeout_sec}s ===\n")
            return 124


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout-sec", type=int, default=3600)
    args = p.parse_args()
    _load_dotenv()
    LOGROOT.mkdir(parents=True, exist_ok=True)

    cells = cells_needing_topup()
    jobs = []
    for c in cells:
        for k in range(c["need"]):
            name = c["name"] if c["need"] == 1 else f"{c['name']}_k{k+1}"
            jobs.append({**c, "name": name})

    plan = {
        "approved_scope": "established_core_topup_only",
        "n_jobs": len(jobs),
        "est_spot_usd": 42,
        "no_scope_AB": True,
        "no_ce_bump": True,
        "jobs": jobs,
    }
    (LOGROOT / "plan.json").write_text(json.dumps(plan, indent=2))
    print(f"Plan: {len(jobs)} jobs → {LOGROOT / 'plan.json'}")
    if args.dry_run:
        for j in jobs:
            print(f"  DRY {j['name']}")
        return

    write_configs(cells)
    state = _load_state()
    if not state.get("started_at"):
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_state(state)

    for j in jobs:
        name = j["name"]
        if name in state["completed"]:
            print(f"SKIP completed {name}")
            continue
        rc = run_one(name, args.timeout_sec)
        if rc == 0:
            state["completed"].append(name)
            print(f"OK {name}")
        else:
            state["failed"].append({"name": name, "rc": rc})
            print(f"FAIL {name} rc={rc}")
        _save_state(state)

    print(
        f"Done. completed={len(state['completed'])} failed={len(state['failed'])}",
        flush=True,
    )
    sys.exit(1 if state["failed"] else 0)


if __name__ == "__main__":
    main()
