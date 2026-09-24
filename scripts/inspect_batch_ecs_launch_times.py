#!/usr/bin/env python3
"""
Pull Batch parent→child timing and ECS container-instance counts for cold vs warm replicas.

Usage (pilot On-Demand JSON):
  PYTHONPATH=. python scripts/inspect_batch_ecs_launch_times.py \\
    --json experiments/results/pilot_ondemand_D5000_N25_rep3_*/batch_*.json

Or explicit job IDs:
  PYTHONPATH=. python scripts/inspect_batch_ecs_launch_times.py \\
    --job-id ad4bd7a2-... --label replica1_cold \\
    --job-id 60e3fe3b-... --label replica3_warm
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _aws(*args: str) -> dict | list:
    region = os.getenv("AWS_REGION", "eu-central-1")
    out = subprocess.check_output(["aws", *args, "--region", region, "--output", "json"])
    return json.loads(out)


def inspect_parent_job(parent_job_id: str, label: str) -> dict:
    children_resp = _aws(
        "batch", "list-jobs",
        "--array-job-id", parent_job_id,
        "--job-status", "SUCCEEDED",
    )
    children = children_resp.get("jobSummaryList", [])
    if not children:
        return {"label": label, "parent_job_id": parent_job_id, "error": "no children"}

    child_ids = [c["jobId"] for c in children]
    # describe_jobs max 100 per call
    desc = _aws("batch", "describe-jobs", "--jobs", *child_ids[:100])
    jobs = desc.get("jobs", [])

    parent_created = min(c["createdAt"] for c in children)
    started_ms = [j["startedAt"] for j in jobs if j.get("startedAt")]
    instances: set[str] = set()
    for j in jobs:
        arn = (j.get("container") or {}).get("containerInstanceArn", "")
        if arn:
            instances.add(arn.split("/")[-1])

    min_started = min(started_ms) if started_ms else None
    max_started = max(started_ms) if started_ms else None

    return {
        "label": label,
        "parent_job_id": parent_job_id,
        "n_children": len(children),
        "unique_container_instances": len(instances),
        "parent_created_to_min_child_started_sec": round((min_started - parent_created) / 1000, 3)
        if min_started
        else None,
        "child_start_spread_sec": round((max_started - min_started) / 1000, 3)
        if min_started and max_started
        else None,
        "cluster_init_from_json_hint": "compare to cluster_init_sec in batch JSON",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Batch results JSON with job_id per replica")
    parser.add_argument("--replica-indices", type=int, nargs="+", default=[0, 2])
    parser.add_argument("--out", type=Path, default=REPO / "tmp" / "batch_ecs_launch_inspect.json")
    args = parser.parse_args()

    jobs: list[tuple[str, str]] = []
    if args.json:
        rows = json.loads(args.json.read_text())
        if not isinstance(rows, list):
            rows = rows.get("runs", [])
        for idx in args.replica_indices:
            for r in rows:
                if int(r.get("replica_index", -1)) == idx:
                    jobs.append((f"replica_{idx + 1}", r["job_id"]))
                    break
    else:
        parser.error("Provide --json from a pilot batch run")

    results = [inspect_parent_job(jid, label) for label, jid in jobs]
    payload = {
        "note": (
            "parent_created_to_min_child_started_sec approximates EC2 launch + ECS register "
            "before first shard starts. Large on replica 1 + small on replica 3 => cold CE."
        ),
        "ce_check": "Both chemo-ec2-worker* CEs have minvCpus=0 (scale-to-zero).",
        "jobs": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
