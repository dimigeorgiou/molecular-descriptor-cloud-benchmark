"""
Compare pre-run estimator output to post-run experiment JSON.

Computes per-(D,N) error and aggregate loss (MAE, MAPE, RMSE) for time and cost.
For mode=compute_only, defaults to comparing computation_sec (fair vs T(N,D) core);
for full_pipeline, compares total_pipeline_sec.

Usage:
  PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \\
    --estimate experiments/results/estimate_paper_replication_low_full_pipeline_20260101_120000.json \\
    --actual experiments/results/batch_full_pipeline_20260101_121500.json

  PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \\
    --estimate path/to/estimate.json --actual path/to/actual.json --json-out experiments/results/verification_report.json

  # After run_experiment.py (creates .../<name>_<ts>/estimation/estimate.json + batch_*.json):
  PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \\
    --run-dir experiments/results/exp_50000_low_full_20260318_170513

  # All run folders for one YAML (matches experiments/results/<name>_*/):
  PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \\
    --from-config experiments/configs/paper_replication_low_full_pipeline.yaml

  Multi-run stdout includes a summary table: primary metric (from --metric) plus
  MAE/RMSE/MAPE/max-abs for cost_usd and total_pipeline_sec on matched (D,N) rows.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

ResolvedMetric = Literal["computation_sec", "total_pipeline_sec", "cost_usd"]
MetricArg = Literal["auto", "computation_sec", "total_pipeline_sec", "cost_usd"]


@dataclass
class ComparisonRow:
    dataset_size: int
    n_nodes: int
    mode: str | None
    metric: str
    estimated: float
    actual: float
    abs_error: float
    pct_error: float | None


def _load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def _resolve_d_key(est: dict[str, Any]) -> int:
    if "requested_dataset_size" in est:
        return int(est["requested_dataset_size"])
    return int(est["dataset_size"])


def _pick_actual_metric(row: dict[str, Any], metric: ResolvedMetric) -> tuple[str, float]:
    """Return (field_name, value) from one actual experiment row."""
    if metric == "computation_sec":
        return "computation_sec", float(row.get("computation_sec", row.get("execution_time", 0.0)))
    if metric == "total_pipeline_sec":
        return "total_pipeline_sec", float(row.get("total_pipeline_sec", 0.0))
    if metric == "cost_usd":
        return "cost_usd", float(row.get("cost_usd", 0.0))
    raise ValueError(f"Unknown metric {metric}")


def _pick_estimate_metric(est: dict[str, Any], metric: ResolvedMetric) -> tuple[str, float]:
    if metric == "computation_sec":
        return "computation_sec", float(est.get("computation_sec", 0.0))
    if metric == "total_pipeline_sec":
        return "total_pipeline_sec", float(est.get("total_pipeline_sec", 0.0))
    if metric == "cost_usd":
        return "estimated_cost_usd", float(est.get("estimated_cost_usd", 0.0))
    raise ValueError(f"Unknown metric {metric}")


def compare_runs(
    estimate_summary: dict[str, Any],
    actual_rows: list[dict[str, Any]],
    metric: MetricArg = "auto",
) -> dict[str, Any]:
    """
    Match estimator per_config entries to actual rows by (dataset_size, n_nodes).

    actual_rows: list of dicts (one batch/local run file format).
    """
    per_config = estimate_summary.get("per_config", [])
    if not per_config:
        raise ValueError("Estimate JSON has no 'per_config' list")

    # Index actual rows by (D, N)
    actual_index: dict[tuple[int, int], dict[str, Any]] = {}
    for row in actual_rows:
        d = int(row.get("dataset_size", 0))
        n = int(row.get("n_nodes", 0))
        actual_index[(d, n)] = row

    rows_out: list[ComparisonRow] = []
    unmatched_estimate: list[dict[str, Any]] = []
    unmatched_actual: set[tuple[int, int]] = set(actual_index.keys())

    for est in per_config:
        d_key = _resolve_d_key(est)
        n_key = int(est["n_nodes"])
        key = (d_key, n_key)
        if key not in actual_index:
            unmatched_estimate.append(est)
            continue

        act = actual_index[key]
        unmatched_actual.discard(key)
        mode = act.get("mode")
        resolved: ResolvedMetric
        if metric == "auto":
            resolved = "computation_sec" if mode == "compute_only" else "total_pipeline_sec"
        else:
            resolved = metric
        _, est_val = _pick_estimate_metric(est, resolved)
        _, act_val = _pick_actual_metric(act, resolved)

        abs_err = abs(act_val - est_val)
        pct = (abs_err / act_val * 100.0) if act_val != 0 else None

        rows_out.append(
            ComparisonRow(
                dataset_size=d_key,
                n_nodes=n_key,
                mode=mode,
                metric=resolved,
                estimated=est_val,
                actual=act_val,
                abs_error=abs_err,
                pct_error=pct,
            )
        )

    def _mae(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def _rmse(vals: list[float]) -> float:
        if not vals:
            return 0.0
        return (sum(v * v for v in vals) / len(vals)) ** 0.5

    def _mape(pcts: list[float | None]) -> float | None:
        clean = [p for p in pcts if p is not None]
        return sum(clean) / len(clean) if clean else None

    abs_errors = [r.abs_error for r in rows_out]
    pcts = [r.pct_error for r in rows_out]

    report = {
        "experiment_name_estimate": estimate_summary.get("experiment_name"),
        "n_matched": len(rows_out),
        "n_unmatched_in_estimate": len(unmatched_estimate),
        "n_unmatched_in_actual": len(unmatched_actual),
        "unmatched_actual_keys": [list(t) for t in sorted(unmatched_actual)],
        "metric_arg": metric,
        "note": (
            "Per-row metric: computation_sec when actual mode is compute_only (auto), "
            "else total_pipeline_sec; use --metric cost_usd for cost comparison."
        ),
        "loss": {
            "mae": round(_mae(abs_errors), 4),
            "rmse": round(_rmse(abs_errors), 4),
            "mape_pct": round(_mape(pcts), 4) if _mape(pcts) is not None else None,
            "max_abs_error": round(max(abs_errors), 4) if abs_errors else 0.0,
        },
        "per_row": [
            {
                "dataset_size": r.dataset_size,
                "n_nodes": r.n_nodes,
                "mode": r.mode,
                "metric": r.metric,
                "estimated": r.estimated,
                "actual": r.actual,
                "abs_error": round(r.abs_error, 6),
                "pct_error": round(r.pct_error, 4) if r.pct_error is not None else None,
            }
            for r in rows_out
        ],
    }
    if unmatched_estimate:
        report["unmatched_estimate_preview"] = [
            {"dataset_size": _resolve_d_key(e), "n_nodes": e.get("n_nodes")} for e in unmatched_estimate[:20]
        ]
    return report


def discover_estimate_json(run_dir: Path) -> Path:
    """Prefer estimation/estimate.json, else newest estimation/estimate_*.json."""
    run_dir = run_dir.resolve()
    direct = run_dir / "estimation" / "estimate.json"
    if direct.is_file():
        return direct
    est_dir = run_dir / "estimation"
    if not est_dir.is_dir():
        raise FileNotFoundError(f"No estimation/ under {run_dir}")
    candidates = sorted(
        est_dir.glob("estimate_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No estimate.json or estimate_*.json under {est_dir}"
        )
    return candidates[0]


def discover_actual_json(run_dir: Path) -> Path:
    """Newest batch_*.json or local_*.json in the run folder (not under estimation/)."""
    run_dir = run_dir.resolve()
    files = [p for p in run_dir.glob("batch_*.json") if p.is_file()] + [
        p for p in run_dir.glob("local_*.json") if p.is_file()
    ]
    if not files:
        raise FileNotFoundError(
            f"No batch_*.json or local_*.json in {run_dir}"
        )
    return max(files, key=lambda p: p.stat().st_mtime)


def collect_run_directories(parent: Path, glob_pattern: str) -> list[Path]:
    """Sorted by mtime (oldest first) so reports follow chronological order."""
    hits = [p for p in parent.glob(glob_pattern) if p.is_dir()]
    return sorted(hits, key=lambda p: p.stat().st_mtime)


def _loss_flat(loss: dict[str, Any]) -> dict[str, Any]:
    """Pick common loss fields for table cells."""
    return {
        "mae": loss.get("mae"),
        "rmse": loss.get("rmse"),
        "mape_pct": loss.get("mape_pct"),
        "max_abs_error": loss.get("max_abs_error"),
    }


def _summarize_multi_report(multi_report: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per run for tabular display."""
    rows: list[dict[str, Any]] = []
    metric_arg = multi_report.get("metric_arg", "auto")
    for entry in multi_report.get("runs", []):
        folder = Path(entry["run_dir"]).name
        row: dict[str, Any] = {"run_folder": folder}
        if entry.get("error"):
            row["status"] = "error"
            row["detail"] = entry["error"]
            rows.append(row)
            continue
        rep = entry.get("report") or {}
        loss = rep.get("loss") or {}
        n_matched = int(rep.get("n_matched", 0))
        n_unmatched_act = int(rep.get("n_unmatched_in_actual", 0))
        row["status"] = "ok"
        row["actual_json"] = Path(entry.get("actual_path", "")).name
        row["n_matched"] = n_matched
        row["n_actual_rows"] = n_matched + n_unmatched_act
        row["primary_metric_arg"] = metric_arg
        prim = _loss_flat(loss)
        row["mae_primary"] = prim["mae"]
        row["rmse_primary"] = prim["rmse"]
        row["mape_primary_pct"] = prim["mape_pct"]
        row["max_abs_primary"] = prim["max_abs_error"]

        rep_cost = entry.get("report_cost") or {}
        cost_loss = _loss_flat(rep_cost.get("loss") or {})
        row["mae_cost_usd"] = cost_loss["mae"]
        row["rmse_cost_usd"] = cost_loss["rmse"]
        row["mape_cost_pct"] = cost_loss["mape_pct"]
        row["max_abs_cost_usd"] = cost_loss["max_abs_error"]

        rep_tp = entry.get("report_total_pipeline") or {}
        tp_loss = _loss_flat(rep_tp.get("loss") or {})
        row["mae_total_pipeline_sec"] = tp_loss["mae"]
        row["rmse_total_pipeline_sec"] = tp_loss["rmse"]
        row["mape_total_pipeline_pct"] = tp_loss["mape_pct"]
        row["max_abs_total_pipeline_sec"] = tp_loss["max_abs_error"]

        rows.append(row)
    return rows


def print_summary_table(multi_report: dict[str, Any]) -> None:
    """Print a markdown-friendly table to stdout."""
    rows = _summarize_multi_report(multi_report)
    if not rows:
        return
    headers = [
        "run_folder",
        "status",
        "actual_json",
        "primary_metric_arg",
        "n_matched",
        "n_actual_rows",
        "mae_primary",
        "rmse_primary",
        "mape_primary_pct",
        "max_abs_primary",
        "mae_cost_usd",
        "rmse_cost_usd",
        "mape_cost_pct",
        "max_abs_cost_usd",
        "mae_total_pipeline_sec",
        "rmse_total_pipeline_sec",
        "mape_total_pipeline_pct",
        "max_abs_total_pipeline_sec",
        "detail",
    ]
    print("\n--- summary table ---", flush=True)
    print("| " + " | ".join(headers) + " |", flush=True)
    print("| " + " | ".join("---" for _ in headers) + " |", flush=True)
    for r in rows:
        cells = []
        for h in headers:
            v = r.get(h, "")
            if v is None:
                v = ""
            cells.append(str(v).replace("|", "\\|"))
        print("| " + " | ".join(cells) + " |", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify estimator accuracy against completed experiment JSON."
    )
    parser.add_argument(
        "--estimate",
        type=Path,
        default=None,
        help="Path to estimate_*.json from experiment_estimator.py",
    )
    parser.add_argument(
        "--actual",
        type=Path,
        default=None,
        help="Path to batch_*.json or local_*.json from run_experiment.py",
    )
    parser.add_argument(
        "--metric",
        choices=["auto", "computation_sec", "total_pipeline_sec", "cost_usd"],
        default="auto",
        help="auto: computation_sec for compute_only actual rows, else total_pipeline_sec",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full report JSON to this path",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        action="append",
        default=None,
        metavar="DIR",
        help=(
            "Experiment results folder with batch_*.json or local_*.json. "
            "With --estimate, uses that JSON instead of estimation/estimate.json. "
            "Repeat for multiple runs."
        ),
    )
    parser.add_argument(
        "--runs-parent",
        type=Path,
        default=Path("experiments/results"),
        help="Base directory for --runs-glob (default: experiments/results)",
    )
    parser.add_argument(
        "--runs-glob",
        type=str,
        default=None,
        help="Glob under --runs-parent for run folders, e.g. 'exp_*_low_full_*'",
    )
    parser.add_argument(
        "--from-config",
        type=Path,
        default=None,
        help=(
            "Experiment YAML; verify all directories --runs-parent/<name>_*/ "
            "where name is the `name` field in that config."
        ),
    )
    parser.add_argument(
        "--print-table",
        action="store_true",
        help="After a multi-run report, print a markdown summary table (stdout).",
    )
    args = parser.parse_args()

    run_dirs: list[Path] = []
    if args.run_dir:
        run_dirs.extend(args.run_dir)
    if args.runs_glob:
        run_dirs.extend(collect_run_directories(args.runs_parent, args.runs_glob))
    if args.from_config:
        with open(args.from_config) as f:
            cfg = yaml.safe_load(f)
        exp_name = (cfg or {}).get("name") or "experiment"
        run_dirs.extend(collect_run_directories(args.runs_parent, f"{exp_name}_*"))

    if run_dirs:
        # Deduplicate while preserving order
        seen: set[Path] = set()
        unique_dirs: list[Path] = []
        for rd in run_dirs:
            key = rd.resolve()
            if key not in seen:
                seen.add(key)
                unique_dirs.append(rd)

        multi_report: dict[str, Any] = {
            "metric_arg": args.metric,
            "fixed_estimate_path": str(args.estimate.resolve()) if args.estimate else None,
            "runs": [],
        }
        fixed_est_data: dict[str, Any] | None = None
        if args.estimate is not None:
            fixed_est_data = _load_json(args.estimate)
            if not isinstance(fixed_est_data, dict):
                raise SystemExit("--estimate must be a JSON object with per_config")

        for rd in unique_dirs:
            entry: dict[str, Any] = {"run_dir": str(rd.resolve())}
            try:
                if fixed_est_data is not None:
                    est_path = args.estimate
                    est_data = fixed_est_data
                    act_path = discover_actual_json(rd)
                    act_data = _load_json(act_path)
                    entry["estimate_path"] = str(est_path.resolve())
                else:
                    est_path = discover_estimate_json(rd)
                    act_path = discover_actual_json(rd)
                    entry["estimate_path"] = str(est_path)
                    act_data = _load_json(act_path)
                    est_data = _load_json(est_path)
                entry["actual_path"] = str(act_path)
            except FileNotFoundError as exc:
                entry["error"] = str(exc)
                multi_report["runs"].append(entry)
                continue
            if not isinstance(est_data, dict):
                entry["error"] = "estimate JSON must be an object with per_config"
                multi_report["runs"].append(entry)
                continue
            if isinstance(act_data, list):
                actual_rows = act_data
            elif isinstance(act_data, dict) and "runs" in act_data:
                actual_rows = act_data["runs"]
            else:
                entry["error"] = "actual JSON must be an array of result rows"
                multi_report["runs"].append(entry)
                continue
            entry["report"] = compare_runs(est_data, actual_rows, metric=args.metric)
            entry["report_cost"] = compare_runs(
                est_data, actual_rows, metric="cost_usd"
            )
            entry["report_total_pipeline"] = compare_runs(
                est_data, actual_rows, metric="total_pipeline_sec"
            )
            multi_report["runs"].append(entry)

        print(json.dumps(multi_report, indent=2))

        if args.print_table or fixed_est_data is not None:
            print_summary_table(multi_report)

        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            with open(args.json_out, "w") as f:
                json.dump(multi_report, f, indent=2)
            print(f"\nMulti-run report written → {args.json_out}", flush=True)
        return

    if args.estimate is None or args.actual is None:
        parser.error(
            "Provide --estimate and --actual, or use --run-dir / --runs-glob / --from-config "
            "(optionally --estimate with --run-dir/--runs-glob to reuse one estimate JSON)."
        )

    est_data = _load_json(args.estimate)
    act_data = _load_json(args.actual)
    if not isinstance(est_data, dict):
        raise SystemExit("--estimate must be a JSON object with per_config")
    if isinstance(act_data, list):
        actual_rows = act_data
    elif isinstance(act_data, dict) and "runs" in act_data:
        actual_rows = act_data["runs"]
    else:
        raise SystemExit("--actual must be a JSON array of result rows")

    report = compare_runs(est_data, actual_rows, metric=args.metric)

    print(json.dumps(report, indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport written → {args.json_out}", flush=True)


if __name__ == "__main__":
    main()
