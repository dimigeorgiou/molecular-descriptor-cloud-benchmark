"""
Derive Batch array-job timing phases from AWS describe_jobs child entries.

Separates queue/cold-start (cluster_init), stagger between children (scheduling),
slowest-shard runtime (computation_sec), and parallel wall clock (cluster_parallel_sec).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class BatchArrayTimings:
    """Measured seconds for one (D, N) array job cluster."""

    cluster_init_sec: float
    scheduling_sec: float
    computation_sec: float
    cluster_parallel_sec: float
    n_children_started: int
    n_children_finished: int

    def total_pipeline_sec(
        self,
        *,
        s3_upload_sec: float,
        result_upload_sec: float = 0.0,
        include_cluster_init: bool = True,
    ) -> float:
        """Sum of measured orchestration + parallel wall (no fabricated sync overhead)."""
        total = float(s3_upload_sec) + float(self.cluster_parallel_sec) + float(result_upload_sec)
        if include_cluster_init:
            total += float(self.cluster_init_sec)
        return round(total, 3)


def _child_runtime_sec(job: Mapping[str, Any]) -> float:
    started = job.get("startedAt") or 0
    stopped = job.get("stoppedAt") or 0
    if started and stopped and stopped >= started:
        return (float(stopped) - float(started)) / 1000.0
    return 0.0


def derive_batch_array_timings(
    child_jobs: Sequence[Mapping[str, Any]],
    *,
    submit_ts_sec: float | None = None,
) -> BatchArrayTimings:
    """
    Compute timing breakdown from Batch array child job descriptions.

    - computation_sec: max per-child (stopped - started) — slowest shard runtime
    - scheduling_sec: max(started) - min(started) among started children
    - cluster_parallel_sec: max(stopped) - min(started) — wall clock user waits
    - cluster_init_sec: min(started)/1000 - submit_ts when submit_ts provided
    """
    started_ms = [
        int(j["startedAt"])
        for j in child_jobs
        if j.get("startedAt")
        and j.get("status") in {"RUNNING", "SUCCEEDED", "FAILED"}
    ]
    stopped_ms = [int(j["stoppedAt"]) for j in child_jobs if j.get("stoppedAt")]

    per_child_runtime = [_child_runtime_sec(j) for j in child_jobs if j.get("startedAt")]

    if started_ms and stopped_ms:
        cluster_parallel_sec = (max(stopped_ms) - min(started_ms)) / 1000.0
        scheduling_sec = (
            (max(started_ms) - min(started_ms)) / 1000.0 if len(started_ms) > 1 else 0.0
        )
        computation_sec = max(per_child_runtime) if per_child_runtime else 0.0
        if submit_ts_sec is not None:
            cluster_init_sec = max(0.0, min(started_ms) / 1000.0 - float(submit_ts_sec))
        else:
            cluster_init_sec = 0.0
    else:
        cluster_parallel_sec = 0.0
        scheduling_sec = 0.0
        computation_sec = 0.0
        cluster_init_sec = 0.0

    return BatchArrayTimings(
        cluster_init_sec=round(cluster_init_sec, 3),
        scheduling_sec=round(scheduling_sec, 3),
        computation_sec=round(computation_sec, 3),
        cluster_parallel_sec=round(cluster_parallel_sec, 3),
        n_children_started=len(started_ms),
        n_children_finished=len(stopped_ms),
    )


def max_shard_wallclock_sec(
    shard_wallclocks: Sequence[float],
) -> float | None:
    """Return max shard wall clock when any positive values exist."""
    positives = [float(w) for w in shard_wallclocks if w and float(w) > 0]
    if not positives:
        return None
    return round(max(positives), 3)


__all__ = ["BatchArrayTimings", "derive_batch_array_timings", "max_shard_wallclock_sec"]
