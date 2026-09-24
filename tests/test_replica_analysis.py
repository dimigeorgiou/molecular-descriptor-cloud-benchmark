"""Tests for replica aggregation helpers."""
from __future__ import annotations

from descriptor_cloud_benchmark.core.replica_analysis import aggregate_replicas, coefficient_of_variation


def test_aggregate_replicas_single_row_degenerate() -> None:
    rows = [
        {
            "experiment_id": "exp",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 25,
            "status": "SUCCEEDED",
            "wall_clock_sec": 180.0,
        }
    ]
    agg = aggregate_replicas(rows)
    key = ("exp", "compute_only", 5000, 25)
    assert agg[key]["n"] == 1
    assert agg[key]["median_wall_clock"] == 180.0
    assert agg[key]["mad"] == 0.0


def test_aggregate_replicas_median_and_mad() -> None:
    rows = [
        {
            "experiment_id": "exp",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 25,
            "status": "SUCCEEDED",
            "wall_clock_sec": 189.4,
        },
        {
            "experiment_id": "exp",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 25,
            "status": "SUCCEEDED",
            "wall_clock_sec": 423.9,
        },
    ]
    agg = aggregate_replicas(rows)
    key = ("exp", "compute_only", 5000, 25)
    assert agg[key]["n"] == 2
    assert agg[key]["median_wall_clock"] == 306.65
    assert agg[key]["mad"] > 100


def test_coefficient_of_variation_spot_swing() -> None:
    cv = coefficient_of_variation([189.4, 423.9])
    assert cv > 0.4
