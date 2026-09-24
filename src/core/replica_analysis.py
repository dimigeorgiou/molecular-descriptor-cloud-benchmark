"""
Aggregate multi-replica benchmark rows for analysis/plotting only.

Raw rows are stored per replica; use these helpers at analysis time.
"""
from __future__ import annotations

import statistics
from typing import Any, Iterable


def _wall_clock(row: dict[str, Any]) -> float:
    wall = row.get("wall_clock_sec")
    if wall is not None:
        return float(wall)
    s3 = float(row.get("s3_upload_sec") or 0)
    init = float(row.get("cluster_init_sec") or 0)
    par = float(row.get("cluster_parallel_sec") or 0)
    total = float(row.get("total_pipeline_sec") or 0)
    if not par and total:
        par = max(total - s3, 0.0)
    return float(s3 + init + par)


def _group_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("experiment_id", ""),
        row.get("mode", ""),
        int(row.get("dataset_size", 0)),
        int(row.get("n_nodes", 0)),
    )


def aggregate_replicas(
    rows: Iterable[dict[str, Any]],
    *,
    wall_key: str = "wall_clock_sec",
) -> dict[tuple[Any, ...], dict[str, float | int]]:
    """
    Group rows by (experiment_id, mode, D, N) and compute replica statistics.

    Returns:
        {
          (exp, mode, D, N): {
            "median_wall_clock": float,
            "mad": float,  # median absolute deviation
            "n": int,
          },
          ...
        }

    Single-replica rows (n=1) are valid degenerate cases.
    """
    buckets: dict[tuple[Any, ...], list[float]] = {}
    for row in rows:
        if row.get("status") not in (None, "SUCCEEDED", "completed"):
            continue
        key = _group_key(row)
        if wall_key == "wall_clock_sec":
            val = _wall_clock(row)
        else:
            val = float(row.get(wall_key) or 0)
        buckets.setdefault(key, []).append(val)

    out: dict[tuple[Any, ...], dict[str, float | int]] = {}
    for key, values in buckets.items():
        if not values:
            continue
        med = float(statistics.median(values))
        if len(values) == 1:
            mad = 0.0
        else:
            mad = float(statistics.median(abs(v - med) for v in values))
        out[key] = {
            "median_wall_clock": round(med, 3),
            "mad": round(mad, 3),
            "n": len(values),
        }
    return out


def coefficient_of_variation(values: list[float]) -> float:
    """CV = stdev / mean; returns 0 if fewer than 2 values or mean is 0."""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean <= 0:
        return 0.0
    return float(statistics.stdev(values) / mean)
