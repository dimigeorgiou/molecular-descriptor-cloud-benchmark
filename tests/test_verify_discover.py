"""Tests for verify_estimate_vs_actual path discovery."""
from __future__ import annotations

from pathlib import Path

from experiments.verify_estimate_vs_actual import (
    _summarize_multi_report,
    compare_runs,
    discover_actual_json,
    discover_estimate_json,
)


def test_discover_estimate_prefers_estimate_json(tmp_path: Path) -> None:
    est_dir = tmp_path / "estimation"
    est_dir.mkdir()
    old = est_dir / "estimate_old.json"
    old.write_text("{}")
    preferred = est_dir / "estimate.json"
    preferred.write_text('{"per_config": []}')
    assert discover_estimate_json(tmp_path) == preferred


def test_discover_estimate_fallback_glob(tmp_path: Path) -> None:
    est_dir = tmp_path / "estimation"
    est_dir.mkdir()
    f = est_dir / "estimate_foo.json"
    f.write_text('{"per_config": []}')
    assert discover_estimate_json(tmp_path) == f


def test_discover_actual_single_batch_file(tmp_path: Path) -> None:
    p = tmp_path / "batch_full_pipeline_x.json"
    p.write_text("[]")
    assert discover_actual_json(tmp_path) == p


def test_summarize_multi_report_includes_cost_and_total_pipeline_errors() -> None:
    est: dict = {
        "per_config": [
            {
                "dataset_size": 1000,
                "n_nodes": 4,
                "computation_sec": 10.0,
                "total_pipeline_sec": 100.0,
                "estimated_cost_usd": 1.0,
            }
        ]
    }
    act = [
        {
            "dataset_size": 1000,
            "n_nodes": 4,
            "mode": "full_pipeline",
            "computation_sec": 12.0,
            "total_pipeline_sec": 120.0,
            "cost_usd": 2.0,
        }
    ]
    multi_report = {
        "metric_arg": "total_pipeline_sec",
        "runs": [
            {
                "run_dir": "/tmp/exp_run_1",
                "actual_path": "/tmp/batch.json",
                "report": compare_runs(est, act, metric="total_pipeline_sec"),
                "report_cost": compare_runs(est, act, metric="cost_usd"),
                "report_total_pipeline": compare_runs(
                    est, act, metric="total_pipeline_sec"
                ),
            }
        ],
    }
    rows = _summarize_multi_report(multi_report)
    assert len(rows) == 1
    r = rows[0]
    assert r["status"] == "ok"
    assert r["mae_primary"] == 20.0
    assert r["mae_cost_usd"] == 1.0
    assert r["mae_total_pipeline_sec"] == 20.0
