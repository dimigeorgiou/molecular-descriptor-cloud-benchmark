"""
Tests for local experiment runner (run_experiment --local).

Uses 100-row CSV fixture and mocks Google Sheets so no real API calls.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


def test_local_experiment_with_100_csv_mock_sheets(
    csv_100_path: Path,
    mock_config_100_path: Path,
    fixtures_dir: Path,
) -> None:
    """Run local experiment with 100-row CSV; Sheets calls are mocked."""
    assert csv_100_path.exists(), "Fixture smiles_100_medium.csv must exist"
    assert mock_config_100_path.exists(), "Config experiment_mock_100.yaml must exist"

    # Ensure config expects 100 and medium so path smiles_100_medium.csv is correct
    import yaml
    with open(mock_config_100_path) as f:
        cfg = yaml.safe_load(f)
    assert cfg["dataset_sizes"] == [100]
    assert cfg.get("smiles_complexity", "medium") == "medium"

    from experiments.run_experiment import run_local_experiment

    with patch("experiments.run_experiment.append_timing_result") as mock_append:
        out_path = run_local_experiment(
            mock_config_100_path,
            override_mode="compute_only",
            dataset_dir=fixtures_dir,
        )

    assert out_path is not None
    assert out_path.exists()
    assert out_path.suffix == ".json"

    import json
    with open(out_path) as f:
        results = json.load(f)
    assert len(results) == 1
    assert results[0]["dataset_size"] == 100
    assert results[0]["n_nodes"] == 1
    assert results[0]["status"] == "completed"
    assert "computation_sec" in results[0]
    assert "total_pipeline_sec" in results[0]

    # Sheets: without GOOGLE_SHEETS_ID we don't call append; with mock we could assert call count
    # Here we did not set env so append_timing_result is not called. If we set it, mock_append would be used.
    # So either we set os.environ and assert mock_append.call_count == 1, or leave as-is.
    # Let's patch so that when sheet_id is set we still don't hit the real API and assert one call per result.
    out_path.unlink(missing_ok=True)


def test_local_experiment_writes_results_and_calls_sheets_when_sheet_id_set(
    csv_100_path: Path,
    mock_config_100_path: Path,
    fixtures_dir: Path,
) -> None:
    """With GOOGLE_SHEETS_ID set, append_timing_result is called once per result (mocked)."""
    import os
    from experiments.run_experiment import run_local_experiment

    with patch("experiments.run_experiment.append_timing_result") as mock_append:
        with patch.dict(os.environ, {"GOOGLE_SHEETS_ID": "mock_sheet_id_123"}):
            out_path = run_local_experiment(
                mock_config_100_path,
                override_mode="compute_only",
                dataset_dir=fixtures_dir,
            )

    assert out_path.exists()
    mock_append.assert_called()
    assert mock_append.call_count == 1
    call_arg = mock_append.call_args[0][1]
    assert call_arg["dataset_size"] == 100
    assert call_arg["n_nodes"] == 1
    out_path.unlink(missing_ok=True)
