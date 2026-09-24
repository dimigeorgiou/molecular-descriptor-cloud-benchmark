"""
AWS Batch job submission helpers.

Selects On-Demand vs Spot queue explicitly (never silently defaulting).
Used by experiments/run_experiment.py for array-job submission.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import boto3
from loguru import logger


def resolve_batch_queue(*, use_spot: bool) -> str:
    """
    Resolve the Batch job queue ARN/name from environment.

    Env vars (first non-empty wins per tier):
      - On-Demand: BATCH_QUEUE_ONDEMAND, BATCH_JOB_QUEUE_ONDEMAND
      - Spot: BATCH_QUEUE_SPOT, BATCH_JOB_QUEUE_SPOT
      - Legacy fallback: BATCH_JOB_QUEUE / AWS_BATCH_JOB_QUEUE (logged as legacy)

    Raises SystemExit if no queue is configured for the requested tier.
    """
    if use_spot:
        for key in ("BATCH_QUEUE_SPOT", "BATCH_JOB_QUEUE_SPOT"):
            val = os.getenv(key, "").strip()
            if val:
                logger.info("Batch queue (SPOT via {}): {}", key, val)
                return val
        legacy = (
            os.getenv("BATCH_JOB_QUEUE") or os.environ.get("AWS_BATCH_JOB_QUEUE") or ""
        ).strip()
        if legacy:
            logger.warning(
                "use_spot=True but BATCH_QUEUE_SPOT unset; using legacy queue {} "
                "(set BATCH_QUEUE_SPOT explicitly)",
                legacy,
            )
            return legacy
        raise SystemExit(
            "use_spot=True requires BATCH_QUEUE_SPOT (or legacy BATCH_JOB_QUEUE)"
        )

    for key in ("BATCH_QUEUE_ONDEMAND", "BATCH_JOB_QUEUE_ONDEMAND"):
        val = os.getenv(key, "").strip()
        if val:
            logger.info("Batch queue (ON-DEMAND via {}): {}", key, val)
            return val
    legacy = (
        os.getenv("BATCH_JOB_QUEUE") or os.environ.get("AWS_BATCH_JOB_QUEUE") or ""
    ).strip()
    if legacy:
        logger.warning(
            "use_spot=False but BATCH_QUEUE_ONDEMAND unset; using legacy queue {} "
            "(set BATCH_QUEUE_ONDEMAND explicitly for replication studies)",
            legacy,
        )
        return legacy
    raise SystemExit(
        "use_spot=False requires BATCH_QUEUE_ONDEMAND (or legacy BATCH_JOB_QUEUE)"
    )


@dataclass
class BatchJobConfig:
    """Configuration for submitting one AWS Batch array job."""

    job_name: str
    job_queue: str
    job_definition: str
    dataset_s3_bucket: str
    dataset_s3_prefix: str
    n_nodes: int
    dataset_size: int
    smiles_complexity: str = "medium"
    descriptor_method: str = "default"
    use_spot: bool = False
    vcpus: int = 4
    memory_mb: int = 8192
    share_identifier: str = "default"
    retry_attempts: int = 2
    extra_environment: Mapping[str, str] = field(default_factory=dict)


def submit_batch_job(config: BatchJobConfig) -> str:
    """
    Submit an AWS Batch array job and return the parent job ID.

    Logs whether On-Demand or Spot queue is used. Adds retryStrategy for
    transient Spot / capacity failures.
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    client = boto3.client("batch", region_name=region)

    pricing_label = "SPOT" if config.use_spot else "ON-DEMAND"
    logger.info(
        "Submitting Batch array job {} ({} queue={}, size={})",
        config.job_name,
        pricing_label,
        config.job_queue,
        config.n_nodes,
    )

    environment = [
        {"name": "DATASET_S3_BUCKET", "value": config.dataset_s3_bucket},
        {"name": "DATASET_S3_PREFIX", "value": config.dataset_s3_prefix},
        {"name": "DATASET_SIZE", "value": str(config.dataset_size)},
        {"name": "N_NODES", "value": str(config.n_nodes)},
        {"name": "SMILES_COMPLEXITY", "value": config.smiles_complexity},
        {"name": "DESCRIPTOR_METHOD", "value": config.descriptor_method},
    ]
    for key, val in config.extra_environment.items():
        environment.append({"name": key, "value": str(val)})

    submit_kwargs: dict[str, Any] = {
        "jobName": config.job_name,
        "jobQueue": config.job_queue,
        "jobDefinition": config.job_definition,
        "containerOverrides": {
            "environment": environment,
        },
        "retryStrategy": {"attempts": max(1, config.retry_attempts)},
    }
    if config.n_nodes > 1:
        submit_kwargs["arrayProperties"] = {"size": config.n_nodes}
    if config.share_identifier:
        submit_kwargs["shareIdentifier"] = config.share_identifier

    response = client.submit_job(**submit_kwargs)
    job_id = response["jobId"]
    logger.info(
        "Submitted Batch job {} → {} ({}, queue={})",
        config.job_name,
        job_id,
        pricing_label,
        config.job_queue,
    )
    return job_id
