"""
Pytest fixtures for chemoinformatics-descriptor-computation tests.

Provides:
  - 100-row SMILES CSV path (tests/fixtures/smiles_100_medium.csv)
  - Mock Google Sheets (gspread) so no real API calls
"""
from __future__ import annotations

from pathlib import Path

import pytest

# Project root (parent of tests/)
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def csv_100_path(fixtures_dir: Path) -> Path:
    """Path to 100-row SMILES CSV (smiles_100_medium.csv)."""
    p = fixtures_dir / "smiles_100_medium.csv"
    if not p.exists():
        pytest.skip(f"Fixture not found: {p}")
    return p


@pytest.fixture
def mock_config_100_path() -> Path:
    """Path to experiment_mock_100.yaml."""
    return PROJECT_ROOT / "experiments" / "configs" / "experiment_mock_100.yaml"
