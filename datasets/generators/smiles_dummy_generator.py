"""
Utility script to generate simple/dummy SMILES datasets.

Use this when you want:
- a file where **all rows contain the same SMILES** (stress-test repeated
  compounds / caching in descriptor tools)
- a file with **different SMILES** at a given overall complexity
- quick mixed–complexity datasets (low/medium/high in one file)

All outputs are CSV files with a **single `smiles` column** by default,
so they can be directly fed into downstream descriptor pipelines.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger

# Support both package and direct-script execution
try:
    from datasets.generators.smiles_generator import (  # type: ignore
        generate_smiles,
        _target_length_for_complexity,
    )
except ModuleNotFoundError:
    from smiles_generator import generate_smiles, _target_length_for_complexity


def _generate_same_smiles_dataset(
    n_rows: int,
    smiles: str | None,
    complexity: str,
    seed: int,
) -> pd.DataFrame:
    """Generate a dataset where every row has the same SMILES string."""
    random.seed(seed)

    if smiles is None:
        target_len = _target_length_for_complexity(complexity)
        smiles = generate_smiles(target_len, complexity)
        logger.info(
            "No SMILES provided, generated base SMILES with complexity={} length≈{}",
            complexity,
            target_len,
        )

    df = pd.DataFrame({"smiles": [smiles] * n_rows})
    return df


def _generate_unique_smiles_dataset(
    n_rows: int,
    complexity: str,
    seed: int,
) -> pd.DataFrame:
    """Generate a dataset with (approximately) unique SMILES strings."""
    random.seed(seed)
    target_len = _target_length_for_complexity(complexity)

    smiles_list: List[str] = []
    seen = set()
    while len(smiles_list) < n_rows:
        s = generate_smiles(target_len, complexity)
        if s in seen:
            continue
        seen.add(s)
        smiles_list.append(s)

    return pd.DataFrame({"smiles": smiles_list})


def _generate_mixed_complexity_dataset(
    n_rows: int,
    seed: int,
) -> pd.DataFrame:
    """
    Generate a dataset that mixes low/medium/high complexity SMILES
    in roughly equal proportions.
    """
    random.seed(seed)
    per_bucket = max(1, n_rows // 3)
    counts = {
        "low": per_bucket,
        "medium": per_bucket,
        "high": n_rows - 2 * per_bucket,
    }

    all_smiles: list[str] = []
    for complexity, count in counts.items():
        if count <= 0:
            continue
        target_len = _target_length_for_complexity(complexity)
        for _ in range(count):
            all_smiles.append(generate_smiles(target_len, complexity))

    random.shuffle(all_smiles)
    return pd.DataFrame({"smiles": all_smiles})


def _write_dataset(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.success("Wrote {} rows → {}", len(df), output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate dummy SMILES CSV files (single-column `smiles`)."
    )

    parser.add_argument(
        "--mode",
        choices=["same", "unique", "mixed"],
        required=True,
        help=(
            "`same`: all rows identical; "
            "`unique`: try to make all SMILES different at one complexity; "
            "`mixed`: low/medium/high mix in one file."
        ),
    )
    parser.add_argument(
        "--rows",
        type=int,
        required=True,
        help="Number of rows (compounds) to generate in the CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to the output CSV file.",
    )
    parser.add_argument(
        "--complexity",
        choices=["low", "medium", "high"],
        default="medium",
        help="Complexity level for `same` and `unique` modes.",
    )
    parser.add_argument(
        "--base-smiles",
        type=str,
        default=None,
        help=(
            "Base SMILES to repeat when mode=`same`. "
            "If omitted, a synthetic one will be generated."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )

    args = parser.parse_args()

    logger.info(
        "Generating dummy SMILES dataset: mode={} rows={} complexity={} output={}",
        args.mode,
        args.rows,
        args.complexity,
        args.output,
    )

    if args.mode == "same":
        df = _generate_same_smiles_dataset(
            n_rows=args.rows,
            smiles=args.base_smiles,
            complexity=args.complexity,
            seed=args.seed,
        )
    elif args.mode == "unique":
        df = _generate_unique_smiles_dataset(
            n_rows=args.rows,
            complexity=args.complexity,
            seed=args.seed,
        )
    else:  # mixed
        df = _generate_mixed_complexity_dataset(
            n_rows=args.rows,
            seed=args.seed,
        )

    _write_dataset(df, args.output)


if __name__ == "__main__":
    main()

