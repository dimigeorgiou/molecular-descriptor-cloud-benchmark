"""Tests for scripts/diagnose_noise_floor.py logic."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPT = REPO / "scripts" / "diagnose_noise_floor.py"


def _load_diagnose():
    spec = importlib.util.spec_from_file_location("diagnose_noise_floor", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_flags_d5000_n25_noise_dominated() -> None:
    mod = _load_diagnose()
    rows = [
        {
            "experiment_id": "paper_replication_low_compute_only",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 25,
            "status": "SUCCEEDED",
            "wall_clock_sec": 189.4,
        },
        {
            "experiment_id": "paper_replication_low_compute_only",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 25,
            "status": "SUCCEEDED",
            "wall_clock_sec": 423.9,
        },
        {
            "experiment_id": "paper_replication_low_compute_only",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 50,
            "status": "SUCCEEDED",
            "wall_clock_sec": 200.0,
        },
        {
            "experiment_id": "paper_replication_low_compute_only",
            "mode": "compute_only",
            "dataset_size": 5000,
            "n_nodes": 75,
            "status": "SUCCEEDED",
            "wall_clock_sec": 210.0,
        },
    ]
    report = mod.diagnose(
        rows,
        experiment_id="paper_replication_low_compute_only",
        mode="compute_only",
    )
    assert any(c["D"] == 5000 and c["N"] == 25 for c in report["multi_run_cells"])
    assert 5000 in report["noise_dominated_D"]
