"""
SMILES dataset generator.

Generates synthetic (plausible) SMILES strings with configurable
dataset sizes and complexity levels, and writes CSV files.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
from loguru import logger
from rich.progress import Progress

try:
    from rdkit import Chem
    from rdkit import RDLogger
except ImportError as exc:  # pragma: no cover - environment-specific
    raise ImportError(
        "RDKit is required for generating valid SMILES. "
        "Install it in your environment, e.g. with:\n"
        "  conda install -c conda-forge rdkit"
    ) from exc

# Silence RDKit valence and parsing warnings which otherwise spam stdout.
RDLogger.DisableLog("rdApp.*")

# Ensure generator logs also go to a rotating file under logs/.
logger.add(
    "logs/logs.log",
    rotation="5 MB",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

# Realistic SMILES building blocks (inspired by SKILLS.md)
ATOMS = ["C", "N", "O", "S", "F", "Cl", "Br"]
BONDS = ["", "=", "#"]
BRANCHES = ["(C)", "(N)", "(O)", "(CC)", "(CCC)", "(c1ccccc1)"]
RINGS = ["c1ccccc1", "C1CCCC1", "c1ccncc1", "C1CCCCC1"]


def _target_length_for_complexity(complexity: str) -> int:
    if complexity == "low":
        return 30
    if complexity == "high":
        return 90
    return 57  # medium / default


def generate_smiles(target_length: int = 57, complexity: str = "medium") -> str:
    """
    Generate a plausible SMILES string of approximate target length.

    This is not a chemistry-accurate generator; it just stitches together
    realistic-looking fragments to approximate descriptor workloads.
    """
    tokens: List[str] = []

    # Start with a ring or atom
    if random.random() < 0.3:
        tokens.append(random.choice(RINGS))
    else:
        tokens.append(random.choice(ATOMS))

    while len("".join(tokens)) < target_length:
        r = random.random()
        if r < 0.5:
            # extend with bond + atom
            bond = random.choice(BONDS)
            atom = random.choice(ATOMS)
            tokens.append(bond + atom)
        elif r < 0.8:
            # add a branch
            tokens.append(random.choice(BRANCHES))
        else:
            # maybe add another ring fragment
            tokens.append(random.choice(RINGS))

    return "".join(tokens)


# Pre-validated templates (RDKit-parseable). Random free-form high SMILES almost
# never validates; rejection sampling can hang for hours — use these instead.
_VALID_TEMPLATES: dict[str, list[str]] = {
    "low": [
        "CCO",
        "CCN",
        "CCC",
        "c1ccccc1",
        "CC(=O)O",
        "CCN(CC)CC",
        "CCOC",
        "CC(C)O",
    ],
    "medium": [
        "CC(=O)Oc1ccccc1C(=O)O",
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
        "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        "c1ccc2c(c1)ccc3c2ccc4c3cccc4",
        "CC1=C(C(=CC=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
        "COC1=C(C=C2C(=C1)CC(C2=O)CC3CCN(CC3)CC(=O)NC4=CC=C(C=C4)F)OC",
    ],
    "high": [
        # ~80–120 char drug-like / polycyclic SMILES (validated offline)
        "CC(C)(C)OC(=O)N[C@@H](CC1=CC=CC=C1)C(=O)N[C@@H](CC(C)C)C(=O)N[C@@H](CCCCN)C(=O)O",
        "CN1CCN(CC1)C2=C(C=C3C(=C2)N=CN=C3NC4=CC(=C(C=C4)F)Cl)OC5CCOC5",
        "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
        "COC1=CC2=C(C=C1OC)C(=NC=N2)NC3=CC(=C(C=C3)OCCCN4CCOCC4)Cl",
        "CC(C)C[C@H](NC(=O)[C@H](Cc1ccccc1)NC(=O)OC(C)(C)C)C(=O)N[C@@H](CCCCN)C(=O)O",
        "C1=CC=C(C=C1)C2=CC(=NN2C3=CC=C(C=C3)S(=O)(=O)N)C(F)(F)F",
        "CCN(CC)CCNC(=O)C1=CC=C(C=C1)N=NC2=CC=CC=C2OCC(=O)O",
        "CC1=CC(=C(C=C1)NC2=NC=CC(=N2)N(C)C3=CC4=NC(=NN4C=C3)C)C",
    ],
}


def _validated_pool(complexity: str) -> list[str]:
    """Return RDKit-validated templates for the complexity tier."""
    raw = _VALID_TEMPLATES.get(complexity, _VALID_TEMPLATES["medium"])
    pool: list[str] = []
    for s in raw:
        if Chem.MolFromSmiles(s) is not None:
            pool.append(s)
    if not pool:
        # Absolute fallback: always-valid ethanol
        pool = ["CCO"]
    return pool


def _extend_smiles_to_length(smiles: str, target_length: int) -> str:
    """
    Lengthen a valid SMILES by appending alkane tails that keep RDKit validity.
    Used for high-complexity approximate length matching.
    """
    if len(smiles) >= target_length:
        return smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return smiles
    # Append carbon chain as a separate fragment joined with '.' is wrong chemically
    # for descriptors; instead concatenate with a phenyl spacer when needed.
    extras = ["CCCC", "c1ccccc1", "CC(=O)N", "OCC"]
    out = smiles
    attempts = 0
    while len(out) < target_length and attempts < 40:
        attempts += 1
        cand = out + extras[attempts % len(extras)]
        if Chem.MolFromSmiles(cand) is not None:
            out = cand
        else:
            # try with an explicit bond to carbon
            cand2 = out + "C"
            if Chem.MolFromSmiles(cand2) is not None:
                out = cand2
            else:
                break
    return out


def generate_dataset(
    n_compounds: int,
    avg_length: int = 57,
    complexity: str = "medium",  # low|medium|high
    output_path: Path | None = None,
    seed: int = 42,
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> pd.DataFrame:
    """
    Generate dataset of SMILES strings. Saves CSV if output_path is given.

    Uses a validated template pool (especially critical for ``high``) so generation
    finishes in seconds rather than hanging on rejection sampling.
    """
    random.seed(seed)
    pool = _validated_pool(complexity)
    smiles_list: List[str] = []
    # Mix: ~70% template (optionally length-extended), ~30% free-form when it validates quickly.
    max_freeform_tries = max(1000, n_compounds // 10)
    freeform_tries = 0
    while len(smiles_list) < n_compounds:
        use_freeform = (
            complexity != "high"
            and freeform_tries < max_freeform_tries
            and random.random() < 0.3
        )
        if use_freeform:
            freeform_tries += 1
            cand = generate_smiles(avg_length, complexity)
            if Chem.MolFromSmiles(cand) is None:
                continue
        else:
            base = random.choice(pool)
            cand = (
                _extend_smiles_to_length(base, avg_length)
                if complexity == "high"
                else base
            )
            if Chem.MolFromSmiles(cand) is None:
                cand = base
        smiles_list.append(cand)
        if progress is not None and task_id is not None:
            progress.advance(task_id)
    df = pd.DataFrame({"smiles": smiles_list})
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info("Saved dataset with {} compounds → {}", n_compounds, output_path)
    return df


def _parse_sizes(values: Iterable[str]) -> list[int]:
    return [int(v) for v in values]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic SMILES datasets."
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        required=True,
        help="Dataset sizes (number of compounds) e.g. 5000 10000",
    )
    parser.add_argument(
        "--complexity",
        choices=["low", "medium", "high"],
        default="medium",
        help="SMILES complexity level (controls average length).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where CSV files will be written.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    target_len = _target_length_for_complexity(args.complexity)
    logger.info(
        "Generating datasets: sizes={} complexity={} target_len={}",
        args.sizes,
        args.complexity,
        target_len,
    )

    with Progress() as progress:
        tasks = {
            size: progress.add_task(
                f"SMILES {size}", total=size
            )
            for size in args.sizes
        }

        for size in args.sizes:
            out_path = output_dir / f"smiles_{size}_{args.complexity}.csv"
            logger.info("Generating SMILES dataset for size={} → {}", size, out_path)
            generate_dataset(
                n_compounds=size,
                avg_length=target_len,
                complexity=args.complexity,
                output_path=out_path,
                seed=args.seed,
                progress=progress,
                task_id=tasks[size],
            )

    logger.success("All datasets generated in {}", output_dir)


if __name__ == "__main__":
    main()

