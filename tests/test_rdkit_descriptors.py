"""
Tests for real RDKit descriptor computation.
"""
from __future__ import annotations

import pytest

pytest.importorskip("rdkit")

from src.worker.rdkit_descriptors import (
    compute_descriptors_for_smiles,
    descriptor_names,
    require_rdkit,
)


def test_descriptor_names_default_non_empty() -> None:
    names = descriptor_names("default")
    assert len(names) >= 200
    assert "MolWt" in names


def test_compute_descriptors_for_smiles_counts() -> None:
    smiles = ["CCO", "c1ccccc1", "invalid!!!", ""]
    stats = compute_descriptors_for_smiles(smiles, method="default")
    assert stats.molecules_processed == 2
    assert stats.molecules_failed == 2
    assert stats.n_descriptors == len(descriptor_names("default"))


def test_require_rdkit_does_not_raise_when_installed() -> None:
    require_rdkit()
