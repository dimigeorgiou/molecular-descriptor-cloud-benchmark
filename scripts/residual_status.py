#!/usr/bin/env python3
"""Quick status for residual campaign orchestrator."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOGROOT = REPO / "tmp/final_campaign/residual"
STATE = LOGROOT / "orchestrator_state.json"
PIDF = LOGROOT / "orchestrator.pid"
PLAN = REPO / "tmp/final_campaign/residual_plan.json"


def main() -> None:
    plan = json.loads(PLAN.read_text()) if PLAN.is_file() else []
    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    completed = state.get("completed", [])
    failed = state.get("failed", [])
    attempts = state.get("attempts", {})
    names = [g["name"] for g in plan]
    pending = [n for n in names if n not in completed and n not in failed]
    pid = PIDF.read_text().strip() if PIDF.is_file() else "?"
    alive = False
    if pid.isdigit():
        try:
            os.kill(int(pid), 0)
            alive = True
        except OSError:
            alive = False
    print(f"orchestrator pid={pid} alive={alive}")
    print(f"progress: {len(completed)}/{len(names)} completed, {len(failed)} failed, {len(pending)} pending")
    if completed:
        print("completed:")
        for n in completed:
            print(f"  OK {n} (attempts={attempts.get(n, '?')})")
    if failed:
        print("failed:")
        for n in failed:
            print(f"  FAIL {n} (attempts={attempts.get(n, '?')})")
    if pending:
        print("next:")
        for n in pending[:5]:
            print(f"  … {n}")
        if len(pending) > 5:
            print(f"  … +{len(pending)-5} more")
    orch = LOGROOT / "orchestrator.out"
    if orch.is_file():
        print("\nlast orch lines:")
        print("\n".join(orch.read_text().splitlines()[-8:]))


if __name__ == "__main__":
    main()
