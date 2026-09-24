"""
Rich-based dashboard for local experiment results.

For now this runs once (no --watch) and renders a summary table
from JSON files in experiments/results/.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.core.model import ModelCoefficients


RESULTS_DIR = Path("experiments/results")


def load_results() -> List[Dict]:
    """
    Load all non-estimate JSON result files from experiments/results/.
    """
    import json

    results: List[Dict] = []
    if not RESULTS_DIR.exists():
        return results
    for fp in sorted(RESULTS_DIR.glob("*.json")):
        if "estimate" in fp.name:
            continue
        with open(fp) as f:
            data = json.load(f)
        if isinstance(data, list):
            results.extend(data)
        elif isinstance(data, dict) and "runs" in data:
            results.extend(data["runs"])
        else:
            results.append(data)
    return results


def render_once() -> None:
    """
    Render a single dashboard view summarizing local experiment results.
    """
    console = Console()
    console.print()
    console.print(Panel("Cheminformatics Descriptor Experiments", border_style="cyan"))

    rows = load_results()
    if not rows:
        console.print("[yellow]No experiment results found in experiments/results/[/]")
        return

    model = ModelCoefficients()

    table = Table(
        title="Local Experiment Runs",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Dataset Size", justify="right", style="cyan")
    table.add_column("Nodes", justify="right", style="green")
    table.add_column("Measured Time (s)", justify="right", style="yellow")
    table.add_column("Predicted Time (s)", justify="right", style="blue")

    for r in rows:
        d = int(r.get("dataset_size", 0))
        n = int(r.get("n_nodes", 0))
        t = float(r.get("execution_time", 0.0))
        t_pred = model.predict(n, d)
        table.add_row(
            f"{d:,}",
            str(n),
            f"{t:.1f}",
            f"{t_pred:.1f}",
        )

    console.print(table)


if __name__ == "__main__":
    render_once()

