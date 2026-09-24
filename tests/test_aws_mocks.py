"""
Placeholder tests for AWS integrations (S3, Batch).

When real AWS code is added, these mocks ensure tests do not call live APIs.
Run with: pytest tests/test_aws_mocks.py -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@patch("boto3.client")
def test_s3_client_mock_upload(mock_boto_client: MagicMock) -> None:
    """Mock S3 client: upload_object (or put_object) can be asserted without real AWS."""
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    # Simulate code that would upload a file to S3
    s3 = mock_boto_client("s3")
    s3.put_object(Bucket="mock-bucket", Key="smiles_100.csv", Body=b"smiles\nC\nCC\n")

    mock_boto_client.assert_called_once_with("s3")
    s3.put_object.assert_called_once()
    call_kw = s3.put_object.call_args[1]
    assert call_kw["Bucket"] == "mock-bucket"
    assert call_kw["Key"] == "smiles_100.csv"


@patch("boto3.client")
def test_batch_client_mock_submit_job(mock_boto_client: MagicMock) -> None:
    """Mock Batch client: submit_job can be asserted without real AWS."""
    mock_batch = MagicMock()
    mock_batch.submit_job.return_value = {"jobId": "mock-job-123"}
    mock_boto_client.return_value = mock_batch

    batch = mock_boto_client("batch")
    result = batch.submit_job(
        jobName="descriptor-100",
        jobQueue="mock-queue",
        jobDefinition="mock-def",
        containerOverrides={"vcpus": 1, "memory": 2048},
    )

    assert result["jobId"] == "mock-job-123"
    mock_batch.submit_job.assert_called_once()
