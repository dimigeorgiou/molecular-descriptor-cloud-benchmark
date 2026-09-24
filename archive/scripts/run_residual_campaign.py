#!/usr/bin/env python3
"""
Sequential residual campaign runner with retries (avoids Batch API stampede).

Runs ONE config at a time from residual_plan.json order.
Retries on EndpointConnectionError / transient failures.

Usage:
  python scripts/run_residual_campaign.py
  python scripts/run_residual_campaign.py --waves 1 2 8
  python scripts/run_residual_campaign.py --max-parallel 1 --retries 3
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "tmp/final_campaign/residual_plan.json"
CFG_DIR = REPO / "experiments/configs/final/residual"
LOGROOT = REPO / "tmp/final_campaign/residual"
PY = os.environ.get("PY", "/opt/anaconda3/envs/venv_chemoinformatics/bin/python")
STATE = LOGROOT / "orchestrator_state.json"


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


def _load_state() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text())
    return {"completed": [], "failed": [], "attempts": {}}


def _save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def _run_one(name: str, wave: int, retry_attempts_env: str | None, timeout_sec: int) -> int:
    cfg = CFG_DIR / f"{name}.yaml"
    if not cfg.is_file():
        print(f"MISSING config {cfg}", flush=True)
        return 2
    log = LOGROOT / f"{name}.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["SKIP_PRE_RUN_ESTIMATE"] = "1"
    env.setdefault("BATCH_RUNNING_DEADLINE_SEC", "1200")
    # Avoid post-write Sheets pivot hang (was zombieing Wave1 for 21h)
    env.setdefault("SHEETS_UPDATE_COMPLEXITY", "0")
    if retry_attempts_env:
        env["BATCH_RETRY_ATTEMPTS"] = retry_attempts_env
    elif wave == 9:
        env["BATCH_RETRY_ATTEMPTS"] = "4"

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
    parser.add_argument("--waves", nargs="*", type=int, default=None)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=6 * 3600,
        help="Per-config wall timeout (default 6h)",
    )
    parser.add_argument("--sleep-between", type=int, default=20)
    parser.add_argument("--force", action="store_true", help="Re-run completed names")
    args = parser.parse_args()

    _load_dotenv()
    LOGROOT.mkdir(parents=True, exist_ok=True)

    if not (CFG_DIR / "residual_w1_d5k_n128_od_medium_r1.yaml").is_file():
        subprocess.check_call([PY, str(REPO / "scripts/generate_residual_configs.py")], cwd=str(REPO))

    gaps = json.loads(PLAN.read_text())
    if args.waves:
        gaps = [g for g in gaps if g["wave"] in set(args.waves)]

    state = _load_state()
    master = LOGROOT / "master.log"

    with master.open("a") as mf:
        mf.write(
            f"\n=== ORCH START {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
            f"jobs={len(gaps)} ===\n"
        )

    for g in gaps:
        name = g["name"]
        if name in state["completed"] and not args.force:
            print(f"SKIP completed {name}", flush=True)
            continue

        attempts = int(state["attempts"].get(name, 0))
        ok = False
        while attempts < args.retries:
            attempts += 1
            state["attempts"][name] = attempts
            _save_state(state)
            ec = _run_one(
                name,
                wave=int(g["wave"]),
                retry_attempts_env=str(g["retry"]) if g.get("retry") else None,
                timeout_sec=args.timeout_sec,
            )
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
            # backoff before retry
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
