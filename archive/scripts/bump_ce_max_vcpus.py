#!/usr/bin/env python3
"""Raise maxvCpus on Batch managed compute environments (needed for N=128+ arrays)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import boto3


def _wait_valid(batch, names: list[str], target: int, timeout_sec: int = 120) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        ok = True
        for ce in names:
            env = batch.describe_compute_environments(computeEnvironments=[ce])[
                "computeEnvironments"
            ][0]
            mv = env.get("computeResources", {}).get("maxvCpus")
            st = env.get("status")
            print(f"{ce}: status={st} maxvCpus={mv}")
            if st != "VALID" or mv != target:
                ok = False
        if ok:
            return
        time.sleep(5)
    raise SystemExit(f"Timed out waiting for CE maxvCpus={target}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Set maxvCpus on chemo Batch CEs (128 nodes × 4 vCPU needs ≥512)."
    )
    p.add_argument("--max-vcpus", type=int, default=1024)
    p.add_argument(
        "--ce",
        action="append",
        default=["chemo-ec2-worker-ondemand", "chemo-ec2-worker"],
        help="Compute environment name (repeatable)",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION", "eu-central-1"),
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    batch = boto3.client("batch", region_name=args.region)
    for ce in args.ce:
        cur = batch.describe_compute_environments(computeEnvironments=[ce])[
            "computeEnvironments"
        ][0]
        old = cur.get("computeResources", {}).get("maxvCpus")
        print(f"{ce}: current maxvCpus={old} → target={args.max_vcpus}")
        if args.dry_run:
            continue
        r = batch.update_compute_environment(
            computeEnvironment=ce,
            computeResources={"maxvCpus": args.max_vcpus},
        )
        print(json.dumps(r, default=str, indent=2))

    if not args.dry_run:
        _wait_valid(batch, args.ce, args.max_vcpus)
        print("OK — all CEs updated")


if __name__ == "__main__":
    main()
