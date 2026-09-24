#!/usr/bin/env python3
"""
Interleaved D=20k / D=40k 2-rep campaign.

Submits 28 cells × 2 replicas, alternating D cell-by-cell so D=20k and D=40k
are not batched hours apart (isolates time-of-day Spot variance).

Order (complexity nested inside N; D alternates every cell):
  N=2  low  D=20k → D=40k
  N=2  med  D=20k → D=40k
  N=4  ...
  ...
  N=128 med D=20k → D=40k

Usage:
  python scripts/run_interleaved_d20_d40.py
  python scripts/run_interleaved_d20_d40.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CFG_DIR = REPO / "experiments/configs/final/interleave"
LOGROOT = REPO / "tmp/final_campaign/interleave"
PY = os.environ.get("PY", "/opt/anaconda3/envs/venv_chemoinformatics/bin/python")
STATE = LOGROOT / "orchestrator_state.json"

POW2 = [2, 4, 8, 16, 32, 64, 128]
COMPLEXITIES = ("low", "medium")
DS = (20000, 40000)


def cell_order() -> list[dict]:
    """28 cells: for each N, for each complexity, D=20k then D=40k."""
    cells = []
    for n in POW2:
        for cx in COMPLEXITIES:
            for d in DS:
                dtag = f"d{d // 1000}k"
                name = f"interleave_{dtag}_n{n}_{cx}_rep2"
                cells.append(
                    {
                        "name": name,
                        "D": d,
                        "N": n,
                        "cx": cx,
                    }
                )
    return cells


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


def write_configs() -> list[dict]:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    cells = cell_order()
    for c in cells:
        body = {
            "mode": "compute_only",
            "smiles_complexity": c["cx"],
            "descriptor_method": "default",
            "vcpus_per_node": 4,
            "gb_per_node": 8,
            "use_spot": True,
            "n_replicas": 2,
            "dataset_dir": "datasets/samples",
            "dataset_sizes": [c["D"]],
            "node_configs": [c["N"]],
        }
        path = CFG_DIR / f"{c['name']}.yaml"
        text = (
            "# Interleaved D=20k/D=40k 2-rep cell (auto)\n"
            "# Alternate D cell-by-cell — do not batch by D.\n"
            f"name: {c['name']}\n"
        ) + yaml.dump(body, default_flow_style=False, sort_keys=False)
        path.write_text(text)
    (LOGROOT).mkdir(parents=True, exist_ok=True)
    (LOGROOT / "cell_order.json").write_text(json.dumps(cells, indent=2))
    return cells


def _load_state() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text())
    return {"completed": [], "failed": [], "attempts": {}}


def _save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def _run_one(name: str, timeout_sec: int) -> int:
    cfg = CFG_DIR / f"{name}.yaml"
    if not cfg.is_file():
        print(f"MISSING config {cfg}", flush=True)
        return 2
    log = LOGROOT / f"{name}.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["SKIP_PRE_RUN_ESTIMATE"] = "1"
    env.setdefault("BATCH_RUNNING_DEADLINE_SEC", "1200")
    env.setdefault("SHEETS_UPDATE_COMPLEXITY", "0")
    env.setdefault("BATCH_RESULT_NOTES", "interleave_d20_d40")
    cmd = [PY, str(REPO / "experiments/run_experiment.py"), "--config", str(cfg)]
    print(
        f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] RUN {name} → {log}",
        flush=True,
    )
    with log.open("a") as lf:
        lf.write(
            f"\n=== START {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n"
        )
        lf.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO),
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
        )
        try:
            return proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
            lf.write(f"\n=== TIMEOUT after {timeout_sec}s — killed ===\n")
            return 124


def _looks_transient(name: str) -> bool:
    log = LOGROOT / f"{name}.log"
    if not log.is_file():
        return False
    tail = log.read_text(errors="replace")[-8000:]
    needles = (
        "EndpointConnectionError",
        "Connection closed",
        "Read timed out",
        "Connect timeout",
        "Temporary failure",
        "BrokenPipeError",
    )
    return any(n in tail for n in needles)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=3 * 3600)
    parser.add_argument("--sleep-between", type=int, default=15)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    _load_dotenv()
    cells = write_configs()
    print(f"cells={len(cells)} arrays={len(cells) * 2}", flush=True)
    for i, c in enumerate(cells, 1):
        print(
            f"  {i:02d}. D={c['D']:<6} N={c['N']:<4} {c['cx']:<7} {c['name']}",
            flush=True,
        )
    if args.dry_run:
        return

    # Datasets must exist
    for d in DS:
        for cx in COMPLEXITIES:
            p = REPO / f"datasets/samples/smiles_{d}_{cx}.csv"
            if not p.is_file():
                raise SystemExit(f"Missing dataset {p}")

    state = _load_state()
    state["scope"] = "interleave_d20_d40_rep2"
    state["order"] = [c["name"] for c in cells]
    _save_state(state)
    master = LOGROOT / "master.log"
    with master.open("a") as mf:
        mf.write(
            f"\n=== ORCH START {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
            f"jobs={len(cells)} ===\n"
        )

    for c in cells:
        name = c["name"]
        if name in state["completed"] and not args.force:
            print(f"SKIP completed {name}", flush=True)
            continue
        attempts = int(state["attempts"].get(name, 0))
        ok = False
        while attempts < args.retries:
            attempts += 1
            state["attempts"][name] = attempts
            _save_state(state)
            ec = _run_one(name, timeout_sec=args.timeout_sec)
            if ec == 0:
                state["completed"].append(name)
                if name in state["failed"]:
                    state["failed"] = [x for x in state["failed"] if x != name]
                _save_state(state)
                print(f"OK {name} (attempt {attempts})", flush=True)
                with master.open("a") as mf:
                    mf.write(f"OK {name} attempt={attempts}\n")
                ok = True
                break
            transient = _looks_transient(name)
            print(
                f"FAIL {name} exit={ec} attempt={attempts}/{args.retries} "
                f"transient={transient}",
                flush=True,
            )
            with master.open("a") as mf:
                mf.write(
                    f"FAIL {name} exit={ec} attempt={attempts} transient={transient}\n"
                )
            if not transient and ec not in (1, 124):
                break
            time.sleep(min(60 * attempts, 300))
        if not ok:
            if name not in state["failed"]:
                state["failed"].append(name)
            _save_state(state)
        time.sleep(args.sleep_between)

    print(
        f"DONE completed={len(state['completed'])} failed={state['failed']}",
        flush=True,
    )
    with master.open("a") as mf:
        mf.write(
            f"=== ORCH END completed={len(state['completed'])} "
            f"failed={state['failed']} ===\n"
        )
    sys.exit(1 if state["failed"] else 0)


if __name__ == "__main__":
    main()
