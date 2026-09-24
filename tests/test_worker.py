"""
Tests for local descriptor computation worker (run_compute).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("rdkit")

from descriptor_cloud_benchmark.worker.compute_descriptors import run_compute


def test_run_compute_100_csv_writes_valid_json(
    csv_100_path: Path,
) -> None:
    """run_compute on 100-row CSV produces a result JSON with real RDKit stats."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out_path = Path(f.name)
    try:
        run_compute(
            dataset_path=csv_100_path,
            n_nodes=1,
            dataset_size=100,
            output_path=out_path,
            smiles_complexity="medium",
            descriptor_method="default",
        )
        assert out_path.exists()
        with open(out_path) as f:
            res = json.load(f)
        assert res["status"] == "completed"
        assert res["dataset_size"] == 100
        assert res["n_nodes"] == 1
        assert res["execution_time"] > 0.0
        assert res["molecules_processed"] == 100
        assert res["n_descriptors"] >= 200
    finally:
        out_path.unlink(missing_ok=True)


def test_run_compute_scales_with_shard_size(csv_100_path: Path) -> None:
    """Larger shard should take at least as long (same molecules, full pass)."""
    import pandas as pd

    df = pd.read_csv(csv_100_path)
    half = df.head(50)
    full = df

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        half_csv = tmp_path / "half.csv"
        full_csv = tmp_path / "full.csv"
        half.to_csv(half_csv, index=False)
        full.to_csv(full_csv, index=False)

        half_out = tmp_path / "half.json"
        full_out = tmp_path / "full.json"

        run_compute(
            dataset_path=half_csv,
            n_nodes=1,
            dataset_size=50,
            output_path=half_out,
        )
        run_compute(
            dataset_path=full_csv,
            n_nodes=1,
            dataset_size=100,
            output_path=full_out,
        )

        with open(half_out) as f:
            half_res = json.load(f)
        with open(full_out) as f:
            full_res = json.load(f)

    assert full_res["execution_time"] >= half_res["execution_time"]
