"""
Tests for Google Sheets helpers (append_timing_result, append_estimate_row_for_config).

All tests mock gspread so no real API or credentials are used.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@patch("descriptor_cloud_benchmark.monitoring.sheets._get_client")
def test_append_timing_result_mock_workbook(mock_get_client: MagicMock) -> None:
    """upsert_timing_result appends when no matching row exists (mocked gspread)."""
    mock_ws = MagicMock()
    mock_ws.row_values.return_value = []
    mock_ws.get_all_values.return_value = []
    mock_sh = MagicMock()
    mock_sh.worksheet.return_value = mock_ws
    mock_gc = MagicMock()
    mock_gc.open_by_key.return_value = mock_sh
    mock_get_client.return_value = mock_gc

    from descriptor_cloud_benchmark.monitoring.sheets import RESULTS_HEADERS, append_timing_result

    result_row = {
        "experiment_id": "test_exp",
        "mode": "compute_only",
        "dataset_size": 100,
        "n_nodes": 1,
        "smiles_complexity": "medium",
        "smiles_avg_length": 32.0,
        "dataset_size_mb": 0.01,
        "s3_upload_sec": 0.0,
        "cluster_init_sec": 60.0,
        "scheduling_sec": 10.0,
        "computation_sec": 15.0,
        "sync_overhead_sec": 2.25,
        "result_upload_sec": 2.0,
        "total_pipeline_sec": 89.25,
        "cost_usd": 0.01,
        "n_star_optimal": "",
        "predicted_computation_sec": "",
        "job_id": "local",
        "status": "completed",
        "notes": "",
    }

    append_timing_result("fake_sheet_id", result_row)

    assert mock_ws.update.called
    mock_ws.append_row.assert_called_once()
    call_args = mock_ws.append_row.call_args[0][0]
    assert len(call_args) == len(RESULTS_HEADERS)


def test_complexity_pivot_query_formula_succeeded_wall_clock() -> None:
    from descriptor_cloud_benchmark.monitoring.sheets import complexity_pivot_query_formula

    f = complexity_pivot_query_formula(
        complexity="low",
        experiment_id="paper_replication_low_compute_only",
        mode="compute_only",
        metric="wall_clock",
        succeeded_only=True,
    )
    assert "AVG(Z)" in f
    assert "T = 'SUCCEEDED'" not in f
    assert "W = 'SUCCEEDED'" in f
    assert "Results!A:Z" in f


def test_complexity_pivot_query_formula_compute_only() -> None:
    from descriptor_cloud_benchmark.monitoring.sheets import complexity_pivot_query_formula

    f = complexity_pivot_query_formula(
        complexity="low",
        experiment_id="smoke_batch_verify",
        mode="compute_only",
        metric="computation",
    )
    assert "AVG(L)" in f
    assert "B = 'smoke_batch_verify'" in f
    assert "F = 'low'" in f
    assert "C = 'compute_only'" in f


def test_complexity_pivot_query_formula_total_pipeline() -> None:
    from descriptor_cloud_benchmark.monitoring.sheets import complexity_pivot_query_formula

    f = complexity_pivot_query_formula(
        complexity="medium",
        experiment_id="paper_replication_medium_compute_only",
        mode="compute_only",
        metric="total_pipeline",
    )
    assert "AVG(O)" in f
    assert "F = 'medium'" in f
    assert "C = 'compute_only'" in f
    assert "B = 'paper_replication_medium_compute_only'" in f


def test_complexity_min_marker_formula() -> None:
    from descriptor_cloud_benchmark.monitoring.sheets import complexity_min_marker_formula

    f = complexity_min_marker_formula(data_col="B", row=3)
    assert "FILTER(B$2:B$15" in f
    assert "A$2:A$15" in f
    assert "D$1" not in f


def test_complexity_experiment_filter_defaults() -> None:
    from descriptor_cloud_benchmark.monitoring.sheets import _complexity_experiment_filter

    assert (
        _complexity_experiment_filter("low", experiment_id=None)
        == "paper_replication_low_compute_only"
    )
    assert _complexity_experiment_filter("low", experiment_id="custom") == "custom"


@patch("descriptor_cloud_benchmark.monitoring.sheets.get_sheet")
def test_append_estimate_row_for_config_mock_worksheet(mock_get_sheet: MagicMock) -> None:
    """append_estimate_row_for_config appends one row with D, N, complexity when get_sheet is mocked."""
    mock_ws = MagicMock()
    mock_ws.row_values.return_value = ["header1", "header2"]
    mock_get_sheet.return_value = mock_ws

    from descriptor_cloud_benchmark.monitoring.sheets import ESTIMATES_HEADERS, append_estimate_row_for_config

    summary = {
        "experiment_name": "test_estimator",
        "config_path": "experiments/configs/examples/experiment_mock_100.yaml",
        "n_jobs": 1,
        "n_dataset_sizes": 1,
        "n_node_configs": 1,
        "n_replicas": 1,
        "total_time_sec": 100.0,
        "total_time_min": 1.67,
        "total_time_hours": 0.03,
        "total_cost_usd": 0.05,
        "use_spot": True,
        "optimal_nodes": {100: 1},
    }
    cfg = {"smiles_complexity": "medium", "descriptor_method": "default"}
    est = {
        "dataset_size": 100,
        "n_nodes": 1,
        "dataset_size_mb": 0.01,
        "s3_upload_sec": 0.0,
        "cluster_init_sec": 60.0,
        "scheduling_sec": 10.0,
        "computation_sec": 12.0,
        "sync_overhead_sec": 1.8,
        "result_upload_sec": 2.0,
        "total_pipeline_sec": 85.8,
        "estimated_cost_usd": 0.05,
    }

    append_estimate_row_for_config("fake_sheet_id", summary, cfg, est)

    mock_ws.append_row.assert_called_once()
    row = mock_ws.append_row.call_args[0][0]
    assert row[14] == 100  # dataset_size
    assert row[15] == 1    # n_nodes
    assert row[16] == "medium"  # complexity_level
    assert len(row) == len(ESTIMATES_HEADERS)
