"""
Experiment Estimator — run BEFORE executing real experiments.

Estimates:
  - Total wall-clock time
  - AWS Batch cost (Spot pricing)
  - Recommended optimal node counts
  - Per-config breakdown

Usage:
  python experiments/estimator/experiment_estimator.py \\
    --config experiments/configs/experiment_01_replication.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
import yaml
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Allow running from project root
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.aws.pricing import (
    SCHEDULING_WARM_SEC,
    blended_cluster_init_sec,
    dual_tier_costs,
    grid_amortized_cluster_init_sec,
    tier_label,
)
from src.core.model import ModelCoefficients
from src.monitoring.sheets import (
    ESTIMATES_HEADERS,
    append_estimate_row_for_config,
    get_sheet,
)

console = Console()


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_model(model_path: Optional[Path]) -> ModelCoefficients:
    if model_path and model_path.exists():
        console.print(f"[green]Using fitted model from:[/] {model_path}")
        return ModelCoefficients.load(model_path)
    try:
        from src.core.model import load_paper_fitted

        model = load_paper_fitted()
        console.print(
            f"[green]Using paper_fitted model (R²={model.r_squared})[/]"
        )
        return model
    except FileNotFoundError:
        pass
    console.print(
        "[yellow]No fitted model — using placeholder_defaults (NOT paper Table 1)[/]"
    )
    return ModelCoefficients.placeholder_defaults()


def _load_dataset_profiles(
    dataset_dir: Optional[Path],
    smiles_complexity: str,
    explicit_files: Optional[Iterable[Path]] = None,
) -> dict[int, dict]:
    """
    Load real dataset metadata from CSV files when available.

    Returns:
      {
        D: {
          "rows": int,
          "dataset_size_mb": float,
          "smiles_avg_length": float,
        },
        ...
      }
    """
    if explicit_files:
        base_paths = [Path(p) for p in explicit_files]
        missing = [p for p in base_paths if not p.exists()]
        if missing:
            console.print(
                f"[yellow]Some explicit dataset files were not found and will be ignored:[/]\n"
                + "\n".join(f"  - {m}" for m in missing)
            )
        smiles_files = [p for p in base_paths if p.exists() and "smiles" in p.stem]
        compound_candidates = [p for p in base_paths if p.exists() and "compounds" in p.stem]
    else:
        if not dataset_dir:
            return {}
        if not dataset_dir.exists():
            console.print(f"[yellow]Dataset directory not found:[/] {dataset_dir}")
            return {}

        # Prefer file name that matches configured complexity for SMILES datasets.
        smiles_preferred = sorted(dataset_dir.glob(f"smiles_*_{smiles_complexity}.csv"))
        smiles_fallback = sorted(dataset_dir.glob("smiles_*.csv"))
        # Also allow synthetic compound (pre-SMILES) datasets.
        compound_candidates = sorted(
            dataset_dir.glob(f"compounds_*_{smiles_complexity}.csv")
        )

        smiles_files = smiles_preferred if smiles_preferred else smiles_fallback

    profiles: dict[int, dict] = {}
    # If we have SMILES datasets, we treat them as ground truth for sizes/lengths.
    # Compound datasets are optional and only used to compute avg_chemical_compound_length.
    candidates = smiles_files

    if not candidates:
        return {}

    import pandas as pd

    for fp in candidates:
        # Expected name like smiles_10000_medium.csv
        parts = fp.stem.split("_")
        if len(parts) < 2:
            continue
        try:
            d = int(parts[1])
        except ValueError:
            continue

        df = pd.read_csv(fp)
        if "smiles" not in df.columns:
            continue
        smiles_col = df["smiles"].astype(str)
        profiles[d] = {
            "rows": int(len(df)),
            "dataset_size_mb": round(fp.stat().st_size / (1024 * 1024), 3),
            "smiles_avg_length": round(float(smiles_col.str.len().mean()), 3),
            "path": str(fp),
        }

    # Optionally augment with pre-SMILES compound length if such datasets exist.
    for fp in compound_candidates:
        parts = fp.stem.split("_")
        if len(parts) < 2:
            continue
        try:
            d = int(parts[1])
        except ValueError:
            continue
        if d not in profiles:
            # We only attach compound stats when we already know about D from SMILES files.
            continue
        df = pd.read_csv(fp)
        if "compound" not in df.columns:
            continue
        comp_col = df["compound"].astype(str)
        profiles[d]["compound_avg_length"] = round(float(comp_col.str.len().mean()), 3)
        profiles[d]["compound_path"] = str(fp)

    return profiles


def _complexity_factor(smiles_complexity: str) -> float:
    """
    Simple multiplier to account for SMILES complexity.

    High-complexity strings are assumed to be slower to parse/featurize.
    """
    mapping = {
        "low": 0.85,
        "medium": 1.0,
        "high": 1.3,
    }
    return mapping.get(smiles_complexity, 1.0)


def _method_factor(descriptor_method: str) -> float:
    """
    Simple multiplier to account for descriptor method choice.

    For example, extended/3D descriptors may take longer than basic 2D ones.
    """
    mapping = {
        "basic": 1.0,
        "default": 1.0,
        "extended": 1.4,
        "heavy": 1.8,
    }
    return mapping.get(descriptor_method, 1.0)


def estimate_config(
    n_nodes: int,
    dataset_size: int,
    model: ModelCoefficients,
    vcpus_per_node: int = 4,
    gb_per_node: float = 8.0,
    use_spot: bool = True,
    smiles_complexity: str = "medium",
    descriptor_method: str = "default",
    dataset_size_mb: float | None = None,
    smiles_avg_length: float | None = None,
    mode: str = "full_pipeline",
    n_replicas: int = 1,
    n_grid_cells: int = 1,
) -> dict:
    """
    Estimate time and cost for one (N, D) configuration, broken down by phase.

    ``mode`` (from experiment YAML) adjusts orchestration heuristics so estimates
    align with ``run_experiment.py`` semantics:

    - ``full_pipeline``: cluster provisioning + scheduler + computation + sync (default).
    - ``compute_only``: omits cold-start cluster init and queue scheduling from the
      pipeline total and cost (isolates descriptor work + minimal I/O).

    Phases:
      - s3_upload_sec
      - cluster_init_sec
      - scheduling_sec
      - computation_sec       (paper T(N,D) × complexity × method)
      - sync_overhead_sec     (fraction of computation; lower in compute_only)
      - result_upload_sec
      - total_pipeline_sec    (sum of listed phases)
    """
    # --- Dataset size approximation (MB) from D and complexity ---
    avg_len_map = {"low": 30, "medium": 57, "high": 90}
    fallback_avg_len = avg_len_map.get(smiles_complexity, 57)
    avg_len = smiles_avg_length if smiles_avg_length is not None else fallback_avg_len
    # If no real file size is provided, approximate CSV bytes.
    if dataset_size_mb is None:
        approx_bytes = dataset_size * (avg_len + 2)
        dataset_size_mb = approx_bytes / (1024 * 1024)

    # --- S3 Upload estimate ---
    bandwidth_mbps = 100.0  # conservative Batch network estimate
    s3_upload_sec = (dataset_size_mb * 8.0) / bandwidth_mbps

    # --- Core computation from paper model + complexity/method multipliers ---
    base_t = model.predict(n_nodes, dataset_size)
    # Prefer measured avg length as effective complexity multiplier around medium=57.
    avg_len_factor = max(0.6, min(2.0, float(avg_len) / 57.0))
    mult = _complexity_factor(smiles_complexity) * avg_len_factor * _method_factor(descriptor_method)
    computation_sec = max(base_t * mult, 10.0)  # at least 10s per job

    # --- Orchestration phases (mode-dependent) ---
    if mode == "compute_only":
        if n_grid_cells > 1:
            cluster_init_sec = grid_amortized_cluster_init_sec(n_grid_cells)
        elif n_replicas > 1:
            cluster_init_sec = blended_cluster_init_sec(n_replicas)
        else:
            from src.aws.pricing import CLUSTER_INIT_COLD_SEC

            cluster_init_sec = CLUSTER_INIT_COLD_SEC
        scheduling_sec = SCHEDULING_WARM_SEC
        sync_overhead_sec = 0.10 * computation_sec
    else:
        # full_pipeline (and unknown modes): paper-style end-to-end overhead
        cluster_init_sec = 60.0
        scheduling_sec = 10.0
        sync_overhead_sec = 0.15 * computation_sec

    result_upload_sec = 2.0  # small JSON

    total_pipeline_sec = (
        s3_upload_sec
        + cluster_init_sec
        + scheduling_sec
        + computation_sec
        + sync_overhead_sec
        + result_upload_sec
    )

    # --- Cost: approximate based on time cluster is "up" (exclude S3 upload) ---
    cluster_lifetime_sec = (
        cluster_init_sec + scheduling_sec + computation_sec + sync_overhead_sec + result_upload_sec
    )
    cost_spot, cost_ondemand = dual_tier_costs(
        n_nodes, float(vcpus_per_node), float(gb_per_node), cluster_lifetime_sec
    )
    cost = cost_spot if use_spot else cost_ondemand

    return {
        "n_nodes": n_nodes,
        "dataset_size": dataset_size,
        "rows": dataset_size,
        "dataset_size_mb": round(dataset_size_mb, 3),
        "smiles_avg_length": round(float(avg_len), 3),
        "s3_upload_sec": round(s3_upload_sec, 1),
        "cluster_init_sec": round(cluster_init_sec, 1),
        "scheduling_sec": round(scheduling_sec, 1),
        "computation_sec": round(computation_sec, 1),
        "sync_overhead_sec": round(sync_overhead_sec, 1),
        "result_upload_sec": round(result_upload_sec, 1),
        "total_pipeline_sec": round(total_pipeline_sec, 1),
        "estimated_cost_usd": round(cost, 4),
        "estimated_cost_spot_usd": round(cost_spot, 4),
        "estimated_cost_ondemand_usd": round(cost_ondemand, 4),
        "smiles_complexity": smiles_complexity,
        "descriptor_method": descriptor_method,
        "mode": mode,
    }


def run_estimator(
    config: dict,
    model: ModelCoefficients,
    verbose: bool = False,
    dataset_dir: Optional[Path] = None,
    dataset_files: Optional[Iterable[Path]] = None,
) -> dict:
    """
    Run full experiment estimation.

    Args:
        config: Loaded YAML experiment config
        model: Performance model coefficients
        verbose: Show per-config breakdown
    """
    dataset_sizes = config.get("dataset_sizes") or []
    node_configs = config.get("node_configs") or []
    vcpus = config.get("vcpus_per_node", 4)
    gb = config.get("gb_per_node", 8.0)
    use_spot = config.get("use_spot", False)
    n_replicas = config.get("n_replicas", 1)
    smiles_complexity = config.get("smiles_complexity", "medium")
    descriptor_method = config.get("descriptor_method", "default")
    exp_mode = config.get("mode", "full_pipeline")
    cfg_dataset_dir = config.get("dataset_dir")
    # CLI args take precedence over config for dataset location.
    effective_dir = dataset_dir or (Path(cfg_dataset_dir) if cfg_dataset_dir else None)
    dataset_profiles = _load_dataset_profiles(
        effective_dir,
        smiles_complexity,
        explicit_files=dataset_files,
    )

    # --- Per-config estimates (grid_pairs or cross-product) ---
    all_estimates: list[dict] = []
    raw_pairs = config.get("grid_pairs")
    if raw_pairs:
        pairs: list[tuple[int, int]] = []
        for item in raw_pairs:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                pairs.append((int(item[0]), int(item[1])))
            else:
                raise ValueError(f"Invalid grid_pairs entry: {item!r}")
        n_grid = len(pairs)
        for d_req, n_nodes in pairs:
            profile = dataset_profiles.get(d_req, {})
            effective_d = int(profile.get("rows", d_req))
            d_size_mb = profile.get("dataset_size_mb")
            d_avg_len = profile.get("smiles_avg_length")
            compound_avg_len = profile.get("compound_avg_length")
            est = estimate_config(
                n_nodes,
                effective_d,
                model,
                vcpus_per_node=vcpus,
                gb_per_node=gb,
                use_spot=use_spot,
                smiles_complexity=smiles_complexity,
                descriptor_method=descriptor_method,
                dataset_size_mb=d_size_mb,
                smiles_avg_length=d_avg_len,
                mode=exp_mode,
                n_replicas=n_replicas,
                n_grid_cells=1 if n_grid == 1 else n_grid,
            )
            est["requested_dataset_size"] = d_req
            if profile:
                est["dataset_path"] = profile.get("path")
                if compound_avg_len is not None:
                    est["compound_avg_length"] = compound_avg_len
            all_estimates.append(est)
    else:
        for D in dataset_sizes:
            profile = dataset_profiles.get(D, {})
            effective_d = int(profile.get("rows", D))
            d_size_mb = profile.get("dataset_size_mb")
            d_avg_len = profile.get("smiles_avg_length")
            compound_avg_len = profile.get("compound_avg_length")
            n_grid = len(dataset_sizes) * len(node_configs)
            for N in node_configs:
                est = estimate_config(
                    N,
                    effective_d,
                    model,
                    vcpus_per_node=vcpus,
                    gb_per_node=gb,
                    use_spot=use_spot,
                    smiles_complexity=smiles_complexity,
                    descriptor_method=descriptor_method,
                    dataset_size_mb=d_size_mb,
                    smiles_avg_length=d_avg_len,
                    mode=exp_mode,
                    n_replicas=n_replicas,
                    n_grid_cells=n_grid,
                )
                est["requested_dataset_size"] = D
                if profile:
                    est["dataset_path"] = profile.get("path")
                    if compound_avg_len is not None:
                        est["compound_avg_length"] = compound_avg_len
                all_estimates.append(est)

    # --- Optimal nodes per dataset ---
    if raw_pairs:
        ds_for_opt = sorted({p[0] for p in pairs})
        nodes_for_opt = sorted({p[1] for p in pairs})
    else:
        ds_for_opt = dataset_sizes
        nodes_for_opt = node_configs
    n_min = min(nodes_for_opt) if nodes_for_opt else 1
    n_max = max(nodes_for_opt) if nodes_for_opt else 1
    optimal = {
        D: model.optimal_nodes(D, n_min=n_min, n_max=n_max) for D in ds_for_opt
    }

    # --- Totals ---
    total_time_sec = sum(e["total_pipeline_sec"] for e in all_estimates) * n_replicas
    total_cost = sum(e["estimated_cost_usd"] for e in all_estimates) * n_replicas
    total_cost_spot = sum(e["estimated_cost_spot_usd"] for e in all_estimates) * n_replicas
    total_cost_ondemand = (
        sum(e["estimated_cost_ondemand_usd"] for e in all_estimates) * n_replicas
    )
    n_jobs = len(all_estimates) * n_replicas
    if raw_pairs:
        unique_d = len({p[0] for p in pairs})
        unique_n = len({p[1] for p in pairs})
    else:
        unique_d = len(dataset_sizes)
        unique_n = len(node_configs)

    return {
        "experiment_name": config.get("name", "unknown"),
        "mode": exp_mode,
        "n_jobs": n_jobs,
        "n_dataset_sizes": unique_d,
        "n_node_configs": unique_n,
        "n_replicas": n_replicas,
        "total_time_sec": total_time_sec,
        "total_time_min": round(total_time_sec / 60, 1),
        "total_time_hours": round(total_time_sec / 3600, 2),
        "total_cost_usd": round(total_cost, 2),
        "total_cost_spot_usd": round(total_cost_spot, 2),
        "total_cost_ondemand_usd": round(total_cost_ondemand, 2),
        "pricing_tier": tier_label(use_spot),
        "use_spot": use_spot,
        "optimal_nodes": optimal,
        "per_config": all_estimates,
    }


def render_summary(summary: dict, verbose: bool = False) -> None:
    """Render estimation summary using Rich."""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{summary['experiment_name']}[/]\n"
            f"[dim]{summary['n_jobs']} jobs = "
            f"{summary['n_dataset_sizes']} dataset sizes × "
            f"{summary['n_node_configs']} node configs × "
            f"{summary['n_replicas']} replica(s)[/]",
            title="🧪 Experiment Estimator",
            border_style="blue",
        )
    )

    # Cost & Time summary (TOTAL PIPELINE)
    t_min = summary["total_time_min"]
    t_hrs = summary["total_time_hours"]
    cost = summary["total_cost_usd"]
    spot_label = summary.get("pricing_tier") or (
        "SPOT" if summary["use_spot"] else "ON-DEMAND"
    )
    cost_spot = summary.get("total_cost_spot_usd", cost)
    cost_od = summary.get("total_cost_ondemand_usd", cost)

    console.print(f"\n[bold]📊 Total Estimate (config tier: {spot_label})[/]")
    console.print(f"  ⏱  Wall time:  [yellow]{t_min:.1f} min[/] ({t_hrs:.2f} hrs)")
    console.print(f"  💰 Est. cost @ tier:  [green]${cost:.2f} USD[/]")
    console.print(f"  💰 Est. SPOT:         [dim]${cost_spot:.2f} USD[/]")
    console.print(f"  💰 Est. ON-DEMAND:    [dim]${cost_od:.2f} USD[/]")
    console.print(f"  🔢 Total jobs: {summary['n_jobs']}\n")

    # Phase breakdown (average over all configs)
    per = summary["per_config"]
    if per:
        n = len(per)
        avg_s3 = sum(e["s3_upload_sec"] for e in per) / n
        avg_cluster = sum(e["cluster_init_sec"] for e in per) / n
        avg_sched = sum(e["scheduling_sec"] for e in per) / n
        avg_comp = sum(e["computation_sec"] for e in per) / n
        avg_sync = sum(e["sync_overhead_sec"] for e in per) / n
        avg_res_up = sum(e["result_upload_sec"] for e in per) / n
        avg_total = sum(e["total_pipeline_sec"] for e in per) / n

        phase_table = Table(
            title="⏱ Phase Estimates (averaged over configs)",
            box=box.SIMPLE,
            show_header=True,
        )
        phase_table.add_column("Phase", style="cyan")
        phase_table.add_column("Est. Time (s)", style="yellow", justify="right")
        phase_table.add_column("Note", style="dim")
        phase_table.add_row("S3 Upload", f"{avg_s3:.1f}", "size/bandwidth, off-cluster")
        phase_table.add_row("Cluster Init", f"{avg_cluster:.1f}", "Batch provisioning")
        phase_table.add_row("Scheduling", f"{avg_sched:.1f}", "queue + scheduler")
        phase_table.add_row("Computation", f"{avg_comp:.1f}", "T(N,D,complexity,method)")
        phase_table.add_row("Sync Overhead", f"{avg_sync:.1f}", "~15% of computation")
        phase_table.add_row("Result Upload", f"{avg_res_up:.1f}", "small JSON")
        phase_table.add_row("TOTAL PIPELINE", f"{avg_total:.1f}", "sum of all phases")
        console.print()
        console.print(phase_table)

    # Optimal nodes table (analytical, computation-only)
    opt_table = Table(
        title="🎯 Optimal Nodes per Dataset (analytical)",
        box=box.ROUNDED,
        show_header=True,
    )
    opt_table.add_column("Dataset Size", style="cyan", justify="right")
    opt_table.add_column("Optimal N*", style="green", justify="center")
    opt_table.add_column("Predicted Time", style="yellow", justify="right")

    # Use same model coefficients as used for estimation (paper default)
    model = ModelCoefficients()
    for D, N_opt in sorted(summary["optimal_nodes"].items()):
        t = model.predict(N_opt, D)
        opt_table.add_row(f"{D:,}", str(N_opt), f"{t:.0f}s ({t/60:.1f}min)")
    console.print(opt_table)

    # Per-config breakdown
    if verbose:
        detail_table = Table(
            title="\n📋 Per-Config Breakdown",
            box=box.SIMPLE,
            show_header=True,
        )
        detail_table.add_column("Dataset (D)", style="cyan", justify="right")
        detail_table.add_column("Nodes (N)", style="magenta", justify="center")
        detail_table.add_column("Rows", style="white", justify="right")
        detail_table.add_column("Avg Len", style="white", justify="right")
        detail_table.add_column("Size MB", style="white", justify="right")
        detail_table.add_column("Est. Time", style="yellow", justify="right")
        detail_table.add_column("Spot $", style="green", justify="right")
        detail_table.add_column("OD $", style="green", justify="right")

        for e in summary["per_config"]:
            detail_table.add_row(
                f"{e['dataset_size']:,}",
                str(e["n_nodes"]),
                f"{e.get('rows', e['dataset_size']):,}",
                f"{e.get('smiles_avg_length', 0):.1f}",
                f"{e.get('dataset_size_mb', 0):.2f}",
                f"{e['total_pipeline_sec']:.0f}s",
                f"${e.get('estimated_cost_spot_usd', e['estimated_cost_usd']):.4f}",
                f"${e.get('estimated_cost_ondemand_usd', e['estimated_cost_usd']):.4f}",
            )
        console.print(detail_table)

    # Recommendation
    if cost > 10:
        console.print(
            Panel(
                f"[bold yellow]⚠️  Estimated cost ${cost:.2f} is significant.[/]\n"
                "Consider:\n"
                "• Running experiment_00_quick.yaml first (sanity check)\n"
                "• Reducing node_configs range\n"
                "• Using fewer dataset_sizes\n"
                "• Ensure use_spot: true in config",
                title="💡 Recommendation",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold green]✅ Estimated cost ${cost:.2f} looks reasonable.[/]\n"
                "Proceed with:\n"
                "  python experiments/run_experiment.py --config <your_config>",
                title="✅ Ready to Run",
                border_style="green",
            )
        )


if __name__ == "__main__":
    # Load environment variables from .env if present
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Estimate time and cost for a cheminformatics experiment"
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to experiment YAML config",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to fitted model JSON (default: use paper estimates)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-config breakdown table",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Save estimate JSON to this path",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="Optional dataset directory; if provided estimator uses real CSV stats.",
    )
    parser.add_argument(
        "--dataset-files",
        nargs="+",
        type=Path,
        default=None,
        help=(
            "Optional explicit list of dataset CSV files to use. "
            "If provided, these override automatic discovery from --dataset-dir. "
            "Filenames should still encode dataset size, e.g. smiles_5000_medium.csv."
        ),
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    mdl = load_model(args.model)
    summary_dict = run_estimator(
        cfg,
        mdl,
        args.verbose,
        dataset_dir=args.dataset_dir,
        dataset_files=args.dataset_files,
    )
    render_summary(summary_dict, args.verbose)

    # Optionally log a high-level estimator summary to Google Sheets (Estimates tab)
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if sheet_id:
        console.print(
            f"[dim]Logging per-config estimates to Google Sheets ID {sheet_id}[/]"
        )
        summary_dict["config_path"] = str(args.config)
        # One open + header check; throttle appends to avoid Sheets 429 read/write quotas.
        interval_sec = float(os.getenv("SHEETS_APPEND_INTERVAL_SEC", "2.5"))
        ws_estimates = get_sheet(sheet_id, "Estimates")
        if not ws_estimates.row_values(1):
            ws_estimates.update("A1", [ESTIMATES_HEADERS])

        per_cf = summary_dict["per_config"]
        for idx, est in enumerate(per_cf):
            try:
                append_estimate_row_for_config(
                    sheet_id,
                    summary_dict,
                    cfg,
                    est,
                    ws=ws_estimates,
                )
            except Exception as exc:  # pragma: no cover
                console.print(
                    f"[red]Failed to append estimate row for D={est['dataset_size']}, "
                    f"N={est['n_nodes']}:[/] {exc}"
                )
                if "429" in str(exc) or "Quota" in str(exc):
                    console.print(
                        f"[yellow]Waiting 65s then retrying once (Sheets rate limit)…[/]"
                    )
                    time.sleep(65.0)
                    try:
                        append_estimate_row_for_config(
                            sheet_id,
                            summary_dict,
                            cfg,
                            est,
                            ws=ws_estimates,
                        )
                    except Exception as exc2:  # pragma: no cover
                        console.print(f"[red]Retry failed:[/] {exc2}")
            if idx + 1 < len(per_cf):
                time.sleep(interval_sec)

    # Always write a local JSON snapshot of this estimation run
    results_dir = Path("experiments/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    if args.save:
        out_path = args.save
    else:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = results_dir / f"estimate_{Path(args.config).stem}_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary_dict, f, indent=2)
    console.print(f"\n[dim]Estimate saved → {out_path}[/]")

