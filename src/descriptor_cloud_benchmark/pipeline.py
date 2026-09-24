"""Thin orchestration helpers for the companion CLI."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="descriptor-cloud-benchmark",
        description=(
            "Companion CLI for Performance and Cost Benchmarking of Cloud Resources "
            "for Large-Scale Molecular Descriptor Computation."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_model = sub.add_parser("model", help="Evaluate T(N,D) / N*(D) with paper coefficients")
    p_model.add_argument("--N", type=int, required=True)
    p_model.add_argument("--D", type=int, required=True)

    p_est = sub.add_parser("estimate", help="Run pre-experiment cost/time estimator")
    p_est.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/examples/experiment_00_quick.yaml"),
    )
    p_est.add_argument("--dataset-dir", type=Path, default=Path("datasets/samples"))

    p_val = sub.add_parser("validate-setup", help="Check env / AWS / packages")

    args = parser.parse_args(argv)

    if args.cmd == "model":
        from descriptor_cloud_benchmark.core.model import ModelCoefficients

        m = ModelCoefficients()
        print(
            f"T(N={args.N}, D={args.D}) = "
            f"{m.predict(n_nodes=args.N, dataset_size=args.D):.3f} s"
        )
        print(f"N*(D={args.D}) = {m.optimal_nodes(dataset_size=args.D)}")
        return 0

    if args.cmd == "estimate":
        import runpy
        import sys

        sys.argv = [
            "experiment_estimator.py",
            "--config",
            str(args.config),
            "--dataset-dir",
            str(args.dataset_dir),
        ]
        runpy.run_path(
            str(Path("experiments/estimator/experiment_estimator.py")),
            run_name="__main__",
        )
        return 0

    if args.cmd == "validate-setup":
        import runpy

        runpy.run_path(str(Path("scripts/validate_setup.py")), run_name="__main__")
        return 0

    return 1
