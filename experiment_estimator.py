"""
Experiment Estimator — Run BEFORE executing real experiments.

Estimates:
  - Total wall-clock time
  - AWS Batch cost (Spot pricing)
  - Recommended optimal node counts
  - Per-config breakdown

Usage:
  python experiments/estimator/experiment_estimator.py \
    --config experiments/configs/experiment_01_replication.yaml

Always review this output before running run_experiment.py!
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

# Allow running from project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.model import ModelCoefficients

console = Console()

# AWS Spot pricing (us-east-1, c5 family, approximate March 2025)
SPOT_VCPU_PRICE_PER_HOUR = 0.012    # per vCPU-hour
SPOT_MEM_PRICE_PER_GB_HOUR = 0.0015  # per GB-hour
ONDEMAND_MULTIPLIER = 3.5            # On-demand is ~3.5x spot


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_model(model_path: Optional[Path]) -> ModelCoefficients:
    if model_path and model_path.exists():
        console.print(f"[green]Using fitted model from:[/] {model_path}")
        return ModelCoefficients.load(model_path)
    console.print("[yellow]No fitted model found — using paper estimates[/]")
    return ModelCoefficients()  # paper estimates


def estimate_config(
    n_nodes: int,
    dataset_size: int,
    model: ModelCoefficients,
    vcpus_per_node: int = 4,
    gb_per_node: float = 8.0,
    use_spot: bool = True,
) -> dict:
    """Estimate time and cost for one (N, D) configuration."""
    t = model.predict(n_nodes, dataset_size)
    t = max(t, 10.0)  # minimum 10s per job

    hours = t / 3600
    total_vcpus = n_nodes * vcpus_per_node
    total_gb = n_nodes * gb_per_node
    price_mult = 1.0 if use_spot else ONDEMAND_MULTIPLIER

    cost = hours * (
        total_vcpus * SPOT_VCPU_PRICE_PER_HOUR +
        total_gb * SPOT_MEM_PRICE_PER_GB_HOUR
    ) * price_mult

    return {
        "n_nodes": n_nodes,
        "dataset_size": dataset_size,
        "estimated_time_sec": round(t, 1),
        "estimated_time_min": round(t / 60, 1),
        "estimated_cost_usd": round(cost, 4),
    }


def run_estimator(config: dict, model: ModelCoefficients, verbose: bool = False) -> dict:
    """
    Run full experiment estimation.

    Args:
        config: Loaded YAML experiment config
        model: Performance model coefficients
        verbose: Show per-config breakdown

    Returns:
        Summary dict with totals and recommendations
    """
    dataset_sizes = config["dataset_sizes"]
    node_configs = config["node_configs"]
    vcpus = config.get("vcpus_per_node", 4)
    gb = config.get("gb_per_node", 8.0)
    use_spot = config.get("use_spot", True)
    n_replicas = config.get("n_replicas", 1)

    # --- Per-config estimates ---
    all_estimates = []
    for D in dataset_sizes:
        for N in node_configs:
            est = estimate_config(N, D, model, vcpus, gb, use_spot)
            all_estimates.append(est)

    # --- Optimal nodes per dataset ---
    optimal = {
        D: model.optimal_nodes(D, n_min=min(node_configs), n_max=max(node_configs))
        for D in dataset_sizes
    }

    # --- Totals ---
    total_time_sec = sum(e["estimated_time_sec"] for e in all_estimates) * n_replicas
    total_cost = sum(e["estimated_cost_usd"] for e in all_estimates) * n_replicas
    n_jobs = len(all_estimates) * n_replicas

    return {
        "experiment_name": config.get("name", "unknown"),
        "n_jobs": n_jobs,
        "n_dataset_sizes": len(dataset_sizes),
        "n_node_configs": len(node_configs),
        "n_replicas": n_replicas,
        "total_time_sec": total_time_sec,
        "total_time_min": round(total_time_sec / 60, 1),
        "total_time_hours": round(total_time_sec / 3600, 2),
        "total_cost_usd": round(total_cost, 2),
        "use_spot": use_spot,
        "optimal_nodes": optimal,
        "per_config": all_estimates,
    }


def render_summary(summary: dict, verbose: bool = False) -> None:
    """Render estimation summary using Rich."""
    console.print()
    console.print(Panel(
        f"[bold cyan]{summary['experiment_name']}[/]\n"
        f"[dim]{summary['n_jobs']} jobs = "
        f"{summary['n_dataset_sizes']} dataset sizes × "
        f"{summary['n_node_configs']} node configs × "
        f"{summary['n_replicas']} replica(s)[/]",
        title="🧪 Experiment Estimator",
        border_style="blue"
    ))

    # Cost & Time summary
    t_min = summary["total_time_min"]
    t_hrs = summary["total_time_hours"]
    cost = summary["total_cost_usd"]
    spot_label = "SPOT" if summary["use_spot"] else "ON-DEMAND"

    console.print(f"\n[bold]📊 Total Estimate ({spot_label} pricing)[/]")
    console.print(f"  ⏱  Wall time:  [yellow]{t_min:.1f} min[/] ({t_hrs:.2f} hrs)")
    console.print(f"  💰 Est. cost:  [green]${cost:.2f} USD[/]")
    console.print(f"  🔢 Total jobs: {summary['n_jobs']}\n")

    # Optimal nodes table
    opt_table = Table(
        title="🎯 Optimal Nodes per Dataset (analytical)",
        box=box.ROUNDED, show_header=True
    )
    opt_table.add_column("Dataset Size", style="cyan", justify="right")
    opt_table.add_column("Optimal N*", style="green", justify="center")
    opt_table.add_column("Predicted Time", style="yellow", justify="right")

    from src.core.model import ModelCoefficients
    model = ModelCoefficients()
    for D, N_opt in sorted(summary["optimal_nodes"].items()):
        t = model.predict(N_opt, D)
        opt_table.add_row(f"{D:,}", str(N_opt), f"{t:.0f}s ({t/60:.1f}min)")
    console.print(opt_table)

    # Per-config breakdown
    if verbose:
        detail_table = Table(
            title="\n📋 Per-Config Breakdown",
            box=box.SIMPLE, show_header=True
        )
        detail_table.add_column("Dataset (D)", style="cyan", justify="right")
        detail_table.add_column("Nodes (N)", style="magenta", justify="center")
        detail_table.add_column("Est. Time", style="yellow", justify="right")
        detail_table.add_column("Est. Cost", style="green", justify="right")

        for e in summary["per_config"]:
            detail_table.add_row(
                f"{e['dataset_size']:,}",
                str(e['n_nodes']),
                f"{e['estimated_time_sec']:.0f}s",
                f"${e['estimated_cost_usd']:.4f}",
            )
        console.print(detail_table)

    # Recommendation
    if cost > 10:
        console.print(Panel(
            f"[bold yellow]⚠️  Estimated cost ${cost:.2f} is significant.[/]\n"
            "Consider:\n"
            "• Running experiment_00_quick.yaml first (sanity check)\n"
            "• Reducing node_configs range\n"
            "• Using fewer dataset_sizes\n"
            "• Ensure use_spot: true in config",
            title="💡 Recommendation",
            border_style="yellow"
        ))
    else:
        console.print(Panel(
            f"[bold green]✅ Estimated cost ${cost:.2f} looks reasonable.[/]\n"
            f"Proceed with:\n"
            f"  python experiments/run_experiment.py --config <your_config>",
            title="✅ Ready to Run",
            border_style="green"
        ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Estimate time and cost for a cheminformatics experiment"
    )
    parser.add_argument(
        "--config", type=Path, required=True,
        help="Path to experiment YAML config"
    )
    parser.add_argument(
        "--model", type=Path, default=None,
        help="Path to fitted model JSON (default: use paper estimates)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show per-config breakdown table"
    )
    parser.add_argument(
        "--save", type=Path, default=None,
        help="Save estimate JSON to this path"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    model = load_model(args.model)
    summary = run_estimator(config, model, args.verbose)
    render_summary(summary, args.verbose)

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        with open(args.save, "w") as f:
            json.dump(summary, f, indent=2)
        console.print(f"\n[dim]Estimate saved → {args.save}[/]")
