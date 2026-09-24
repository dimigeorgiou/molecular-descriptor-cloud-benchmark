"""
RDKit molecular descriptor computation for shard workers.

Computes the full RDKit 2D descriptor set (Descriptors._descList) per molecule.
Used by Batch containers and local experiments — no simulated timing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from loguru import logger

try:
    from rdkit import Chem
    from rdkit import RDLogger
    from rdkit.Chem import Descriptors
    from rdkit.ML.Descriptors import MoleculeDescriptors
except ImportError as exc:  # pragma: no cover - optional at import in non-RDKit envs
    Chem = None  # type: ignore[assignment,misc]
    Descriptors = None  # type: ignore[assignment,misc]
    MoleculeDescriptors = None  # type: ignore[assignment,misc]
    _RDKIT_IMPORT_ERROR = exc
else:
    RDLogger.DisableLog("rdApp.*")
    _RDKIT_IMPORT_ERROR = None


SUPPORTED_METHODS = frozenset({"default"})


@dataclass(frozen=True)
class DescriptorComputeStats:
    """Aggregate stats from one shard descriptor pass."""

    molecules_processed: int
    molecules_failed: int
    n_descriptors: int
    descriptor_method: str

    @property
    def total_descriptor_values(self) -> int:
        return self.molecules_processed * self.n_descriptors


def require_rdkit() -> None:
    if Chem is None or Descriptors is None or MoleculeDescriptors is None:
        raise ImportError(
            "RDKit is required for descriptor computation. "
            "Install with: conda install -c conda-forge rdkit"
        ) from _RDKIT_IMPORT_ERROR


def descriptor_names(method: str = "default") -> list[str]:
    """Return ordered descriptor names for the given method."""
    require_rdkit()
    if method not in SUPPORTED_METHODS:
        raise ValueError(
            f"Unsupported descriptor_method={method!r}; supported: {sorted(SUPPORTED_METHODS)}"
        )
    return [name for name, _ in Descriptors._descList]


def compute_descriptors_for_smiles(
    smiles_list: Sequence[str] | Iterable[str],
    *,
    method: str = "default",
) -> DescriptorComputeStats:
    """
    Compute all RDKit 2D descriptors for each SMILES string.

    Values are computed and discarded — this path is for benchmarking compute
    cost, not persisting descriptor matrices.
    """
    require_rdkit()
    names = descriptor_names(method)
    calculator = MoleculeDescriptors.MolecularDescriptorCalculator(names)

    processed = 0
    failed = 0
    for raw in smiles_list:
        smi = str(raw).strip()
        if not smi:
            failed += 1
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            failed += 1
            continue
        # Force full descriptor evaluation (217 values for default method).
        calculator.CalcDescriptors(mol)
        processed += 1

    stats = DescriptorComputeStats(
        molecules_processed=processed,
        molecules_failed=failed,
        n_descriptors=len(names),
        descriptor_method=method,
    )
    logger.debug(
        "RDKit shard: processed={} failed={} descriptors={}",
        processed,
        failed,
        len(names),
    )
    return stats
