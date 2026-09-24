#!/usr/bin/env python3
"""Set minScaleDownDelayMinutes on a Batch managed CE (boto3; newer than some AWS CLI builds)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import boto3


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ce", default="chemo-ec2-worker-ondemand")
    p.add_argument("--minutes", type=int, default=20)
    p.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "eu-central-1"))
    args = p.parse_args()

    batch = boto3.client("batch", region_name=args.region)
    r = batch.update_compute_environment(
        computeEnvironment=args.ce,
        computeResources={"scalingPolicy": {"minScaleDownDelayMinutes": args.minutes}},
    )
    print(json.dumps(r, default=str, indent=2))

    for _ in range(12):
        d = batch.describe_compute_environments(computeEnvironments=[args.ce])
        env = d["computeEnvironments"][0]
        sp = env.get("computeResources", {}).get("scalingPolicy")
        if env.get("status") == "VALID" and sp:
            print(f"OK {args.ce} scalingPolicy={sp}")
            return
        time.sleep(10)
    print("WARN: CE not VALID or scalingPolicy not visible yet", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
