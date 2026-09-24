"""
Register (or update) AWS Batch job definition for the RDKit shard worker.

Uses BATCH_IMAGE_URI and AWS_BATCH_JOB_DEFINITION from the environment.
Falls back to describing the latest revision of the named job definition for
container resource defaults when present.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _latest_container_props(batch_client, job_def_name: str) -> dict:
    resp = batch_client.describe_job_definitions(
        jobDefinitionName=job_def_name,
        status="ACTIVE",
    )
    defs = resp.get("jobDefinitions", [])
    if not defs:
        return {}
    latest = max(defs, key=lambda d: d.get("revision", 0))
    return latest.get("containerProperties", {})


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    image = os.environ.get("BATCH_IMAGE_URI")
    if not image:
        logger.error("Set BATCH_IMAGE_URI to the ECR image URI (tag included).")
        raise SystemExit(1)

    job_def_name = os.environ.get("AWS_BATCH_JOB_DEFINITION", "chemo-ec2-worker")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
    vcpus = int(os.getenv("BATCH_VCPUS", "4"))
    memory_mb = int(os.getenv("BATCH_MEMORY_MB", "8192"))

    batch = boto3.client("batch", region_name=region)
    prev = _latest_container_props(batch, job_def_name)
    prev_full = batch.describe_job_definitions(
        jobDefinitionName=job_def_name,
        status="ACTIVE",
    )["jobDefinitions"]
    prev_def = max(prev_full, key=lambda d: d.get("revision", 0)) if prev_full else {}

    container = {
        "image": image,
        "vcpus": vcpus,
        "memory": memory_mb,
        "command": [],
        "environment": [],
        "jobRoleArn": prev.get("jobRoleArn"),
        "executionRoleArn": prev.get("executionRoleArn"),
        "volumes": prev.get("volumes", []),
        "mountPoints": prev.get("mountPoints", []),
        "ulimits": prev.get("ulimits", []),
        "linuxParameters": prev.get("linuxParameters"),
        "logConfiguration": prev.get("logConfiguration"),
        "secrets": prev.get("secrets", []),
        "networkConfiguration": prev.get("networkConfiguration"),
        "fargatePlatformConfiguration": prev.get("fargatePlatformConfiguration"),
        "enableExecuteCommand": prev.get("enableExecuteCommand"),
    }
    # Drop None keys — Batch rejects null optional fields.
    container = {k: v for k, v in container.items() if v is not None}

    register_kwargs = {
        "jobDefinitionName": job_def_name,
        "type": "container",
        "containerProperties": container,
        "platformCapabilities": prev_def.get("platformCapabilities") or ["EC2"],
    }
    if prev_def.get("schedulingPriority") is not None:
        register_kwargs["schedulingPriority"] = prev_def["schedulingPriority"]
    else:
        register_kwargs["schedulingPriority"] = int(os.getenv("BATCH_SCHEDULING_PRIORITY", "1"))
    if prev.get("retryStrategy"):
        register_kwargs["retryStrategy"] = prev["retryStrategy"]
    if prev.get("timeout"):
        register_kwargs["timeout"] = prev["timeout"]

    resp = batch.register_job_definition(**register_kwargs)
    logger.success(
        "Registered {} revision {} → {}",
        resp["jobDefinitionName"],
        resp["revision"],
        image,
    )
    print(json.dumps(resp, indent=2, default=str))


if __name__ == "__main__":
    main()
