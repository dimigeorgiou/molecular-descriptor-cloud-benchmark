"""Tests for paper Table 1+2 fitted coefficients (PDF transcription only)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.model import (
    _EXPECTED_PAPER_ROW_COUNT,
    _PAPER_EXECUTION_TIMES_PATH,
    _PAPER_FITTED_PATH,
    _PAPER_TABLE1_PATH,
    fit_paper_table1_model,
    load_paper_execution_rows,
    load_paper_fitted,
    load_paper_table1_rows,
)


def test_paper_execution_times_has_full_grid() -> None:
    rows = load_paper_execution_rows()
    assert len(rows) == _EXPECTED_PAPER_ROW_COUNT


def test_legacy_replication_json_rejected() -> None:
    if not _PAPER_TABLE1_PATH.is_file():
        pytest.skip("legacy replication json removed")
    with pytest.raises(ValueError, match="Invalid provenance|replication"):
        load_paper_table1_rows(_PAPER_TABLE1_PATH)


def test_paper_fitted_high_r_squared() -> None:
    model = fit_paper_table1_model()
    assert model.source == "paper_fitted"
    assert model.r_squared is not None
    assert model.r_squared >= 0.85, (
        f"paper_fitted R²={model.r_squared:.4f} — check PDF transcription, not replication data"
    )
    assert model.fitted_from_n_samples == len(load_paper_execution_rows())
    assert model.d > 0, "convex U-curve requires d > 0"


@pytest.mark.skipif(not _PAPER_EXECUTION_TIMES_PATH.exists(), reason="paper execution json missing")
def test_load_paper_fitted_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "paper_fitted_model.json"
    monkeypatch.setattr("src.core.model._PAPER_FITTED_PATH", cache)
    m1 = load_paper_fitted(cache, refit=True)
    m2 = load_paper_fitted(cache)
    assert m1.source == "paper_fitted"
    assert m2.a == m1.a
    assert cache.is_file()
