"""
Descriptor computation worker (local and Batch shard).

Runs real RDKit 2D descriptor computation; execution_time is measured wall clock.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from descriptor_cloud_benchmark.worker.rdkit_descriptors import compute_descriptors_for_smiles


def _read_smiles_column(dataset_path: Path) -> list[str]:
    df = pd.read_csv(dataset_path)
    if "smiles" not in df.columns:
        raise ValueError(f"CSV must contain a 'smiles' column: {dataset_path}")
    return df["smiles"].astype(str).tolist()


def run_compute(
    dataset_path: Path,
    n_nodes: int,
    dataset_size: int | None,
    output_path: Path,
    smiles_complexity: str = "medium",
    descriptor_method: str = "default",
) -> None:
    """
    Compute RDKit descriptors for all rows in dataset_path and write result JSON.

    ``execution_time`` is wall-clock seconds for the descriptor loop on this shard.
    ``n_nodes`` is recorded for experiment metadata (shard size is implicit in CSV rows).
    """
    start = time.perf_counter()
    smiles_list = _read_smiles_column(dataset_path)
    actual_size = len(smiles_list)
    d_size = dataset_size or actual_size

    stats = compute_descriptors_for_smiles(smiles_list, method=descriptor_method)
    end = time.perf_counter()
    wall_sec = end - start

    result = {
        "dataset_size": int(d_size),
        "shard_rows": int(actual_size),
        "n_nodes": int(n_nodes),
        "execution_time": round(wall_sec, 3),
        "wallclock_overhead_sec": round(wall_sec, 3),
        "smiles_complexity": smiles_complexity,
        "descriptor_method": descriptor_method,
        "molecules_processed": stats.molecules_processed,
        "molecules_failed": stats.molecules_failed,
        "n_descriptors": stats.n_descriptors,
        "status": "completed",
        "job_id": "local",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(
        "Compute done: shard_rows={} D={} N={} exec_time={:.1f}s method={} → {}",
        actual_size,
        d_size,
        n_nodes,
        wall_sec,
        descriptor_method,
        output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descriptor computation worker (RDKit 2D descriptors)."
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        required=True,
        help="Path to input SMILES CSV.",
    )
    parser.add_argument(
        "--n-nodes",
        type=int,
        required=True,
        help="Cluster size N (metadata for experiments).",
    )
    parser.add_argument(
        "--dataset-size",
        type=int,
        default=None,
        help="Logical dataset size D (defaults to number of rows).",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
        help="Where to write JSON result.",
    )
    parser.add_argument(
        "--smiles-complexity",
        type=str,
        default="medium",
        help="Complexity label to record in result.",
    )
    parser.add_argument(
        "--descriptor-method",
        type=str,
        default="default",
        help="Descriptor set identifier (default: full RDKit 2D set).",
    )
    args = parser.parse_args()

    run_compute(
        dataset_path=args.dataset_path,
        n_nodes=args.n_nodes,
        dataset_size=args.dataset_size,
        output_path=args.output_path,
        smiles_complexity=args.smiles_complexity,
        descriptor_method=args.descriptor_method,
    )


if __name__ == "__main__":
    main()
