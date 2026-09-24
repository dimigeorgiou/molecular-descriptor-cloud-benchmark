"""Tests for Batch array timing decomposition."""
from __future__ import annotations

from descriptor_cloud_benchmark.core.batch_timing import derive_batch_array_timings, max_shard_wallclock_sec


def test_derive_batch_array_timings_separates_scheduling_and_compute() -> None:
    """Slowest shard runtime must not include scheduling stagger in computation_sec."""
    submit_ts = 1_000.0
    child_jobs = [
        {"startedAt": 1_010_000, "stoppedAt": 1_020_000, "status": "SUCCEEDED"},  # 10s
        {"startedAt": 1_030_000, "stoppedAt": 1_040_000, "status": "SUCCEEDED"},  # 10s, +20s stagger
    ]
    t = derive_batch_array_timings(child_jobs, submit_ts_sec=submit_ts)
    assert t.computation_sec == 10.0
    assert t.scheduling_sec == 20.0
    assert t.cluster_parallel_sec == 30.0
    assert t.cluster_init_sec == 10.0


def test_derive_batch_array_timings_empty_children() -> None:
    t = derive_batch_array_timings([], submit_ts_sec=100.0)
    assert t.computation_sec == 0.0
    assert t.cluster_parallel_sec == 0.0


def test_max_shard_wallclock_sec() -> None:
    assert max_shard_wallclock_sec([1.2, 3.4, 0.0]) == 3.4
    assert max_shard_wallclock_sec([]) is None
    assert max_shard_wallclock_sec([0.0, 0.0]) is None
