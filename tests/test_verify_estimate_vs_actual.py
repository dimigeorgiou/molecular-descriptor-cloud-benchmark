"""Tests for experiments/verify_estimate_vs_actual.py."""
from __future__ import annotations

from pathlib import Path

from experiments.verify_estimate_vs_actual import compare_runs


def test_compare_runs_matches_d_n_and_mae() -> None:
    estimate = {
        "experiment_name": "test",
        "per_config": [
            {
                "n_nodes": 25,
                "dataset_size": 5000,
                "requested_dataset_size": 5000,
                "computation_sec": 10.0,
                "total_pipeline_sec": 100.0,
                "estimated_cost_usd": 0.01,
            },
        ],
    }
    actual = [
        {
            "dataset_size": 5000,
            "n_nodes": 25,
            "mode": "compute_only",
            "computation_sec": 12.0,
            "total_pipeline_sec": 50.0,
            "cost_usd": 0.02,
        }
    ]
    report = compare_runs(estimate, actual, metric="auto")
    assert report["n_matched"] == 1
    assert report["loss"]["mae"] == 2.0
    assert report["per_row"][0]["metric"] == "computation_sec"


def test_compare_runs_full_pipeline_uses_total() -> None:
    estimate = {
        "experiment_name": "test",
        "per_config": [
            {
                "n_nodes": 50,
                "dataset_size": 10000,
                "computation_sec": 20.0,
                "total_pipeline_sec": 120.0,
                "estimated_cost_usd": 0.05,
            },
        ],
    }
    actual = [
        {
            "dataset_size": 10000,
            "n_nodes": 50,
            "mode": "full_pipeline",
            "computation_sec": 18.0,
            "total_pipeline_sec": 130.0,
            "cost_usd": 0.04,
        }
    ]
    report = compare_runs(estimate, actual, metric="auto")
    assert report["per_row"][0]["metric"] == "total_pipeline_sec"
    assert report["loss"]["mae"] == 10.0


def test_compare_runs_cost_metric() -> None:
    estimate = {
        "experiment_name": "test",
        "per_config": [
            {
                "n_nodes": 10,
                "dataset_size": 1000,
                "estimated_cost_usd": 0.1,
                "computation_sec": 1.0,
                "total_pipeline_sec": 2.0,
            },
        ],
    }
    actual = [
        {
            "dataset_size": 1000,
            "n_nodes": 10,
            "mode": "full_pipeline",
            "cost_usd": 0.12,
        }
    ]
    report = compare_runs(estimate, actual, metric="cost_usd")
    assert abs(report["loss"]["mae"] - 0.02) < 1e-9
