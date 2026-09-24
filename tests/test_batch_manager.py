"""Tests for AWS Batch queue resolution and submit kwargs."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.aws.batch_manager import BatchJobConfig, resolve_batch_queue, submit_batch_job


def test_resolve_batch_queue_ondemand_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BATCH_QUEUE_ONDEMAND", "chemo-ondemand-queue")
    monkeypatch.delenv("BATCH_QUEUE_SPOT", raising=False)
    assert resolve_batch_queue(use_spot=False) == "chemo-ondemand-queue"


def test_resolve_batch_queue_spot_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BATCH_QUEUE_SPOT", "chemo-spot-queue")
    assert resolve_batch_queue(use_spot=True) == "chemo-spot-queue"


@patch("src.aws.batch_manager.boto3.client")
def test_submit_batch_job_includes_retry_strategy(mock_boto: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.submit_job.return_value = {"jobId": "job-1"}
    mock_boto.return_value = mock_client

    cfg = BatchJobConfig(
        job_name="test-D5000-N25",
        job_queue="q",
        job_definition="def",
        dataset_s3_bucket="b",
        dataset_s3_prefix="pfx",
        n_nodes=25,
        dataset_size=5000,
        use_spot=False,
        retry_attempts=2,
    )
    job_id = submit_batch_job(cfg)
    assert job_id == "job-1"
    kwargs = mock_client.submit_job.call_args[1]
    assert kwargs["retryStrategy"] == {"attempts": 2}
    assert kwargs["arrayProperties"] == {"size": 25}


@patch("src.aws.batch_manager.boto3.client")
def test_submit_batch_job_n1_is_not_array(mock_boto: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.submit_job.return_value = {"jobId": "job-solo"}
    mock_boto.return_value = mock_client

    cfg = BatchJobConfig(
        job_name="test-D5000-N1",
        job_queue="q",
        job_definition="def",
        dataset_s3_bucket="b",
        dataset_s3_prefix="pfx",
        n_nodes=1,
        dataset_size=5000,
        use_spot=False,
    )
    assert submit_batch_job(cfg) == "job-solo"
    kwargs = mock_client.submit_job.call_args[1]
    assert "arrayProperties" not in kwargs
