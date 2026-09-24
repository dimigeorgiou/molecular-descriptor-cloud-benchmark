"""
Synthetic chemical compound string generator.

Generates one-column CSVs with a `compound` field that mimics
pre-SMILES molecule strings. These are intended to be upstream
inputs on which a separate pipeline applies SMILES transformation.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger


def _target_length_for_complexity(complexity: str) -> int:
    if complexity == "low":
        return 20
    if complexity == "high":
        return 80
    return 40  # medium / default


PREFIXES = [
    "methyl",
    "ethyl",
    "propyl",
    "butyl",
    "hydroxy",
    "amino",
    "chloro",
    "bromo",
    "nitro",
]

CORES = [
    "benzene",
    "pyridine",
    "pyrimidine",
    "indole",
    "phenyl",
    "naphthalene",
]

SUFFIXES = [
    "carboxylate",
    "chloride",
    "sulfate",
    "nitrate",
    "phosphate",
    "hydrochloride",
]


def generate_compound(target_length: int = 40, complexity: str = "medium") -> str:
    """
    Generate a pseudo-chemical compound name-like string.

    This is NOT chemically accurate; it just mimics realistic
    text lengths and structure to approximate upstream workload.
    """
    tokens: List[str] = []

    # Always start with a core scaffold
    tokens.append(random.choice(CORES))

    # Add modifiers until we reach approximate target length
    while len(" ".join(tokens)) < target_length:
        r = random.random()
        if r < 0.5:
            tokens.insert(0, random.choice(PREFIXES))
        elif r < 0.85:
            tokens.append(random.choice(PREFIXES))
        else:
            tokens.append(random.choice(SUFFIXES))

    return " ".join(tokens)


def generate_dataset(
    n_compounds: int,
    avg_length: int = 40,
    complexity: str = "medium",
    output_path: Path | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate dataset of pseudo compound strings. Saves CSV if output_path is given.
    """
    random.seed(seed)
    compounds = [generate_compound(avg_length, complexity) for _ in range(n_compounds)]
    df = pd.DataFrame({"compound": compounds, "id": range(n_compounds)})
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info("Saved compound dataset with {} rows → {}", n_compounds, output_path)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic chemical compound (pre-SMILES) datasets."
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
        help="Complexity level (controls average compound string length).",
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
        "Generating compound datasets: sizes={} complexity={} target_len={}",
        args.sizes,
        args.complexity,
        target_len,
    )

    for size in args.sizes:
        out_path = output_dir / f"compounds_{size}_{args.complexity}.csv"
        generate_dataset(
            n_compounds=size,
            avg_length=target_len,
            complexity=args.complexity,
            output_path=out_path,
            seed=args.seed,
        )

    logger.success("All compound datasets generated in {}", output_dir)


if __name__ == "__main__":
    main()

