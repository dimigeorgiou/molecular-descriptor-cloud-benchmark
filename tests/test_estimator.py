"""
Tests for experiment estimator (run_estimator with 100-row CSV).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.model import ModelCoefficients
from experiments.estimator.experiment_estimator import (
    estimate_config,
    load_config,
    run_estimator,
)


def test_estimator_with_100_csv(
    csv_100_path: Path,
    mock_config_100_path: Path,
) -> None:
    """run_estimator with explicit 100-row file returns summary with per_config for D=100."""
    cfg = load_config(mock_config_100_path)
    model = ModelCoefficients.placeholder_defaults()
    summary = run_estimator(
        cfg,
        model,
        verbose=False,
        dataset_dir=None,
        dataset_files=[csv_100_path],
    )

    assert summary["experiment_name"] == "experiment_mock_100"
    assert summary["n_dataset_sizes"] == 1
    assert summary["n_node_configs"] == 1
    assert summary["n_jobs"] == 1
    per = summary["per_config"]
    assert len(per) == 1
    assert per[0]["dataset_size"] == 100
    assert per[0]["n_nodes"] == 1
    assert "total_pipeline_sec" in per[0]
    assert "estimated_cost_usd" in per[0]
    assert summary["optimal_nodes"].get(100) is not None
    assert summary.get("mode") == cfg.get("mode", "full_pipeline")


def test_compute_only_warm_replica_blend_and_dual_pricing() -> None:
    """compute_only uses empirical CE init; both Spot and On-Demand costs are emitted."""
    model = ModelCoefficients.placeholder_defaults()
    cold = estimate_config(25, 5000, model, mode="compute_only", n_replicas=1)
    warm = estimate_config(25, 5000, model, mode="compute_only", n_replicas=10)
    assert cold["cluster_init_sec"] == 140.0
    assert 55 < warm["cluster_init_sec"] < 140
    assert warm["estimated_cost_ondemand_usd"] > warm["estimated_cost_spot_usd"]
