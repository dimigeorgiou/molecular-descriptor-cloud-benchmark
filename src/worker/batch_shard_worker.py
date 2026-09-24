"""
AWS Batch shard worker entrypoint.

Run inside the Batch container (one array child per shard). Reads:
  DATASET_S3_BUCKET, DATASET_S3_PREFIX, AWS_BATCH_JOB_ARRAY_INDEX (optional)

Downloads shard_{i}.csv from S3, runs descriptor compute, uploads result JSON.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import boto3
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.worker.compute_descriptors import run_compute


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _s3_download_file(s3: boto3.client, bucket: str, key: str, dest: str) -> None:
    s3.download_file(bucket, key, dest)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _s3_upload_file(s3: boto3.client, src: str, bucket: str, key: str) -> None:
    s3.upload_file(src, bucket, key)


def main() -> None:
    bucket = os.environ["DATASET_S3_BUCKET"]
    prefix = os.environ["DATASET_S3_PREFIX"].rstrip("/")
    shard_index = int(os.environ.get("AWS_BATCH_JOB_ARRAY_INDEX", "0"))
    n_nodes = int(os.environ.get("N_NODES", "1"))
    dataset_size = int(os.environ.get("DATASET_SIZE", "0"))
    complexity = os.environ.get("SMILES_COMPLEXITY", "medium")
    descriptor_method = os.environ.get("DESCRIPTOR_METHOD", "default")

    shard_key = f"{prefix}/shard_{shard_index}.csv"
    s3 = boto3.client("s3")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        local_csv = tmp_path / "shard.csv"
        local_out = tmp_path / "result.json"

        logger.info("Downloading s3://{}/{}", bucket, shard_key)
        try:
            _s3_download_file(s3, bucket, shard_key, str(local_csv))
        except Exception as exc:
            # Empty trailing shards used to be skipped on upload; tolerate missing keys.
            msg = str(exc)
            if "404" in msg or "Not Found" in msg or "NoSuchKey" in msg:
                logger.warning(
                    "Shard key missing (empty shard fallback): s3://{}/{} ({})",
                    bucket,
                    shard_key,
                    type(exc).__name__,
                )
                local_csv.write_text("smiles\n", encoding="utf-8")
            else:
                raise


        t0 = time.perf_counter()
        run_compute(
            dataset_path=local_csv,
            n_nodes=n_nodes,
            dataset_size=dataset_size or None,
            output_path=local_out,
            smiles_complexity=complexity,
            descriptor_method=descriptor_method,
        )
        wall_sec = round(time.perf_counter() - t0, 3)

        with open(local_out) as f:
            payload = json.load(f)
        payload["wallclock_sec"] = wall_sec
        payload["shard_index"] = shard_index
        with open(local_out, "w") as f:
            json.dump(payload, f, indent=2)

        result_key = f"{prefix}/results/shard_{shard_index}.json"
        _s3_upload_file(s3, str(local_out), bucket, result_key)
        logger.success(
            "Shard {} done wallclock={}s → s3://{}/{}",
            shard_index,
            wall_sec,
            bucket,
            result_key,
        )


if __name__ == "__main__":
    main()
