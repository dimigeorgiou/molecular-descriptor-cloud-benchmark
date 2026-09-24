"""
S3 dataset upload and existence checks.
"""
from __future__ import annotations

from pathlib import Path

import boto3
from loguru import logger


def upload_dataset(local_path: Path, bucket: str, s3_key: str) -> str:
    """
    Upload a local CSV dataset to S3 and return the s3:// URI.
    """
    s3 = boto3.client("s3")
    s3.upload_file(
        str(local_path),
        bucket,
        s3_key,
        ExtraArgs={"ServerSideEncryption": "AES256"},
    )
    uri = f"s3://{bucket}/{s3_key}"
    logger.success("Uploaded {} → {}", local_path.name, uri)
    return uri


def check_or_upload(local_path: Path, bucket: str, s3_key: str) -> str:
    """
    Upload the dataset only if it does not already exist in S3.
    """
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=s3_key)
        logger.info("Dataset already in S3: s3://{}/{}", bucket, s3_key)
    except s3.exceptions.ClientError:
        upload_dataset(local_path, bucket, s3_key)
    return f"s3://{bucket}/{s3_key}"

