"""
Google Sheets synchronization helpers.

Not required for local/offline experiments, but implemented following SKILLS.md.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from typing import Dict, List, Any

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


RESULTS_HEADERS: List[str] = [
    "Timestamp",
    "Experiment ID",
    "Mode",
    "Dataset Size (D)",
    "Nodes (N)",
    "SMILES Complexity",
    "Avg SMILES Length",
    "Dataset Size (MB)",
    "S3 Upload (s)",
    "Cluster Init (s)",
    "Scheduling (s)",
    "Computation (s)",
    "Sync Overhead (s)",
    "Result Upload (s)",
    "Total Pipeline (s)",
    "Cost (USD)",
    "Pricing Tier",
    "Cost Spot Equiv (USD)",
    "Cost On-Demand Equiv (USD)",
    "N* Optimal",
    "Predicted Computation (s)",
    "Job ID",
    "Status",
    "Notes",
    "Cluster Parallel (s)",
    "Wall Clock (s)",
]

# Results column letters for QUERY (must match RESULTS_HEADERS order).
_METRIC_COLUMNS: dict[str, str] = {
    "computation": "L",
    "total_pipeline": "O",
    "cluster_parallel": "Y",
    "wall_clock": "Z",
}
_RESULTS_QUERY_RANGE = "Results!A:Z"

ESTIMATES_HEADERS: List[str] = [
    "timestamp",
    "experiment_name",
    "config_path",
    "n_jobs",
    "n_dataset_sizes",
    "n_node_configs",
    "n_replicas",
    "total_time_sec",
    "total_time_min",
    "total_time_hours",
    "total_cost_usd",
    "total_cost_spot_usd",
    "total_cost_ondemand_usd",
    "pricing_mode (SPOT / ON-DEMAND)",
    "dataset_size",
    "n_nodes",
    "complexity_level",
    "complexity_score",
    "avg_chemical_compound_length",
    "expected_smiles_length",
    "dataset_size_mb",
    "s3_upload_sec",
    "cluster_init_sec",
    "scheduling_sec",
    "computation_sec",
    "sync_overhead_sec",
    "result_upload_sec",
    "total_pipeline_sec",
    "estimated_cost_usd",
    "estimated_cost_spot_usd",
    "estimated_cost_ondemand_usd",
    "n_star_optimal",
]


def _get_client() -> gspread.Client:
    """
    Create an authenticated gspread client.

    Resolution order for the service account JSON file:
      1. GOOGLE_SERVICE_ACCOUNT_JSON env var (if it points to an existing file)
      2. config/google_service_account.json
      3. credentials/google_service_account.json

    This makes it robust if the env var was not loaded or if the file
    lives under config/ as in your current setup.
    """
    candidates = []
    env_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_path:
        candidates.append(env_path)
    candidates.extend(
        [
            "config/google_service_account.json",
            "credentials/google_service_account.json",
        ]
    )

    json_path: str | None = None
    for path in candidates:
        if path and Path(path).exists():
            json_path = path
            break

    if json_path is None:
        raise FileNotFoundError(
            "Could not find a Google service account JSON file. "
            "Checked GOOGLE_SERVICE_ACCOUNT_JSON, "
            "config/google_service_account.json and "
            "credentials/google_service_account.json."
        )

    creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    logger.info("Using Google service account credentials from {}", json_path)
    return gspread.authorize(creds)


def get_sheet(sheet_id: str, worksheet_name: str):
    """
    Authenticate using a service account JSON and return a worksheet handle.
    Creates the worksheet if it does not exist.
    """
    gc = _get_client()
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=40)
    return ws


def _ensure_results_header(sheet_id: str) -> None:
    ws = get_sheet(sheet_id, "Results")
    try:
        existing = ws.row_values(1)
    except gspread.GSpreadException:
        existing = []
    if existing != RESULTS_HEADERS:
        # Do NOT shrink rows here (can conflict with frozen rows).
        # Just overwrite the first row with our header.
        ws.update("A1", [RESULTS_HEADERS])
        logger.info("Ensured 'Results' header row in Google Sheets.")


def append_result(sheet_id: str, result: Dict[str, Any]) -> None:
    """
    Backwards-compatible minimal append (legacy schema).
    Prefer append_timing_result for new experiments.
    """
    # Ensure sheet exists but do not enforce new header schema here.
    ws = get_sheet(sheet_id, "Results")
    row = [
        datetime.utcnow().isoformat(),
        result.get("experiment_id", ""),
        result.get("dataset_size", ""),
        result.get("n_nodes", ""),
        result.get("execution_time", ""),
        result.get("cost_usd", ""),
        result.get("smiles_complexity", ""),
        result.get("job_id", ""),
        result.get("status", ""),
    ]
    ws.append_row(row)
    logger.info(
        "Sheet (legacy) updated for D={}, N={}",
        result.get("dataset_size"),
        result.get("n_nodes"),
    )


def _timing_result_to_row(result: Dict[str, Any]) -> list[Any]:
    """Build a Results row list from a timing result dict."""

    def _get(key: str) -> Any:
        val = result.get(key)
        return "" if val is None else val

    s3 = float(_get("s3_upload_sec") or 0)
    init = float(_get("cluster_init_sec") or 0)
    par = float(_get("cluster_parallel_sec") or 0)
    total = float(_get("total_pipeline_sec") or 0)
    if not par and total:
        par = max(total - s3, 0.0)
    wall = result.get("wall_clock_sec")
    if wall is None:
        wall = round(s3 + init + par, 3)

    return [
        datetime.utcnow().isoformat(),
        _get("experiment_id"),
        _get("mode"),
        _get("dataset_size"),
        _get("n_nodes"),
        _get("smiles_complexity"),
        _get("smiles_avg_length"),
        _get("dataset_size_mb"),
        _get("s3_upload_sec"),
        _get("cluster_init_sec"),
        _get("scheduling_sec"),
        _get("computation_sec"),
        _get("sync_overhead_sec"),
        _get("result_upload_sec"),
        _get("total_pipeline_sec"),
        _get("cost_usd"),
        _get("pricing_tier"),
        _get("cost_spot_usd"),
        _get("cost_ondemand_usd"),
        _get("n_star_optimal"),
        _get("predicted_computation_sec"),
        _get("job_id"),
        _get("status"),
        _get("notes"),
        round(par, 3) if par else "",
        round(float(wall), 3) if wall else "",
    ]


def _row_score(row: list[str], idx: dict[str, int]) -> tuple[int, int, str]:
    """Higher is better: SUCCEEDED first, then rows with wall clock, then newest ts."""
    status = row[idx["Status"]] if len(row) > idx["Status"] else ""
    succeeded = 1 if status == "SUCCEEDED" else 0
    w_i = idx.get("Wall Clock (s)", 25)
    has_wall = 1 if len(row) > w_i and row[w_i] not in ("", None) else 0
    ts = row[idx["Timestamp"]] if len(row) > idx["Timestamp"] else ""
    return (succeeded, has_wall, ts)


def _pad_row(row: list[str], width: int) -> list[str]:
    if len(row) < width:
        return row + [""] * (width - len(row))
    return row[:width]


def _derive_cluster_parallel_and_wall(row: list[str], idx: dict[str, int]) -> tuple[float, float]:
    """Derive cluster_parallel (V) and wall_clock (W) from existing phase columns."""
    s3 = float(row[idx["S3 Upload (s)"]] or 0) if len(row) > idx["S3 Upload (s)"] else 0.0
    init = float(row[idx["Cluster Init (s)"]] or 0) if len(row) > idx["Cluster Init (s)"] else 0.0
    total = float(row[idx["Total Pipeline (s)"]] or 0) if len(row) > idx["Total Pipeline (s)"] else 0.0
    v_i = idx.get("Cluster Parallel (s)", 21)
    w_i = idx.get("Wall Clock (s)", 25)
    par = float(row[v_i] or 0) if len(row) > v_i and row[v_i] else 0.0
    if not par and total:
        par = max(total - s3, 0.0)
    wall = float(row[w_i] or 0) if len(row) > w_i and row[w_i] else 0.0
    if not wall:
        wall = round(s3 + init + par, 3)
    return round(par, 3), round(wall, 3)


def backfill_results_derived_metrics(sheet_id: str) -> int:
    """Fill Cluster Parallel (V) and Wall Clock (W) on every Results data row."""
    _ensure_results_header(sheet_id)
    ws = get_sheet(sheet_id, "Results")
    rows = ws.get_all_values()
    if len(rows) < 2:
        return 0
    idx = {h: i for i, h in enumerate(rows[0])}
    width = len(RESULTS_HEADERS)
    updates: list[dict[str, Any]] = []
    changed = 0
    for row_num, row in enumerate(rows[1:], start=2):
        row = _pad_row(row, width)
        par, wall = _derive_cluster_parallel_and_wall(row, idx)
        v_i = idx["Cluster Parallel (s)"]
        w_i = idx["Wall Clock (s)"]
        old_par = row[v_i] if len(row) > v_i else ""
        old_wall = row[w_i] if len(row) > w_i else ""
        if str(old_par) != str(par) or str(old_wall) != str(wall):
            changed += 1
            row[v_i] = str(par) if par else ""
            row[w_i] = str(wall) if wall else ""
            updates.append({"range": f"A{row_num}", "values": [row[:width]]})
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    logger.info("Backfilled derived metrics on {} Results rows", changed)
    return changed


def dedupe_paper_compute_results(sheet_id: str) -> dict[str, int]:
    """
    Keep one row per (experiment_id, D, N) for paper_replication compute_only runs.
    Updates the earliest row in place with the best duplicate; deletes extras.
    """
    _ensure_results_header(sheet_id)
    ws = get_sheet(sheet_id, "Results")
    rows = ws.get_all_values()
    if len(rows) < 2:
        return {"kept": 0, "deleted": 0, "updated": 0}

    header = rows[0]
    idx = {h: i for i, h in enumerate(header)}
    width = len(RESULTS_HEADERS)

    groups: dict[tuple[str, str, str, str], list[tuple[int, list[str]]]] = {}
    for row_num, row in enumerate(rows[1:], start=2):
        row = _pad_row(row, width)
        exp = row[idx["Experiment ID"]]
        mode = row[idx["Mode"]]
        if "paper_replication" not in exp or mode != "compute_only":
            continue
        key = (exp, mode, row[idx["Dataset Size (D)"]], row[idx["Nodes (N)"]])
        groups.setdefault(key, []).append((row_num, row))

    delete_rows: list[int] = []
    updated = 0
    for key, entries in groups.items():
        if len(entries) <= 1:
            continue
        entries.sort(key=lambda e: e[0])
        keep_row_num, keep_row = entries[0]
        best = max((e[1] for e in entries), key=lambda r: _row_score(r, idx))
        par, wall = _derive_cluster_parallel_and_wall(best, idx)
        best = _pad_row(best, width)
        best[idx["Cluster Parallel (s)"]] = str(par) if par else ""
        best[idx["Wall Clock (s)"]] = str(wall) if wall else ""
        if best != keep_row:
            ws.update(f"A{keep_row_num}", [best[:width]], value_input_option="USER_ENTERED")
            updated += 1
        delete_rows.extend(row_num for row_num, _ in entries[1:])

    deleted = 0
    for row_num in sorted(delete_rows, reverse=True):
        ws.delete_rows(row_num)
        deleted += 1

    logger.info(
        "Deduped paper compute_only Results: updated={}, deleted={}",
        updated,
        deleted,
    )
    return {"kept": len(groups), "deleted": deleted, "updated": updated}


def _replica_index_from_result(result: Dict[str, Any]) -> int:
    """Replica index for upsert key; 0 for legacy single-run rows."""
    if "replica_index" in result and result["replica_index"] is not None:
        return int(result["replica_index"])
    notes = str(result.get("notes", ""))
    if "replica=" in notes:
        try:
            part = notes.split("replica=")[1].split("/")[0].split(";")[0].strip()
            return max(0, int(part) - 1)
        except (ValueError, IndexError):
            pass
    return 0


def upsert_timing_result(sheet_id: str, result: Dict[str, Any]) -> None:
    """
    Update an existing Results row for (experiment_id, mode, D, N, replica) or append.
    """
    _ensure_results_header(sheet_id)
    ws = get_sheet(sheet_id, "Results")
    rows = ws.get_all_values()
    idx = {h: i for i, h in enumerate(rows[0] if rows else RESULTS_HEADERS)}
    width = len(RESULTS_HEADERS)

    exp = str(result.get("experiment_id", ""))
    mode = str(result.get("mode", ""))
    d = str(result.get("dataset_size", ""))
    n = str(result.get("n_nodes", ""))
    replica = str(_replica_index_from_result(result))

    target_row: int | None = None
    for row_num, row in enumerate(rows[1:], start=2):
        row = _pad_row(row, width)
        row_notes = row[idx["Notes"]] if len(row) > idx["Notes"] else ""
        row_replica = str(_replica_index_from_result({"notes": row_notes}))
        if (
            row[idx["Experiment ID"]] == exp
            and row[idx["Mode"]] == mode
            and str(row[idx["Dataset Size (D)"]]) == d
            and str(row[idx["Nodes (N)"]]) == n
            and row_replica == replica
        ):
            target_row = row_num
            break

    new_row = _timing_result_to_row(result)
    if target_row is not None:
        ws.update(f"A{target_row}", [new_row], value_input_option="USER_ENTERED")
        logger.info("Timing result updated in-place row {} exp={} D={} N={}", target_row, exp, d, n)
    else:
        ws.append_row(new_row)
        logger.info("Timing result appended (no existing row) exp={} D={} N={}", exp, d, n)

    try:
        update_phase_summary(sheet_id)
        update_timing_breakdown_chart_data(sheet_id)
        if os.getenv("SHEETS_UPDATE_COMPLEXITY", "1").strip().lower() in {"1", "true", "yes"}:
            update_complexity_analysis_tabs(sheet_id)
    except Exception as exc:  # pragma: no cover - external service
        logger.warning("Failed to update summary sheets: {}", exc)


def append_timing_result(sheet_id: str, result: Dict[str, Any]) -> None:
    """
    Write a full timing result row to the 'Results' worksheet.

    Default: upsert in place on (experiment_id, mode, D, N). Set SHEETS_APPEND_ONLY=1
    to restore legacy append behaviour.
    """
    if os.getenv("SHEETS_APPEND_ONLY", "").strip().lower() in {"1", "true", "yes"}:
        _ensure_results_header(sheet_id)
        ws = get_sheet(sheet_id, "Results")
        ws.append_row(_timing_result_to_row(result))
        logger.info(
            "Timing result appended for exp_id={} D={} N={}",
            result.get("experiment_id"),
            result.get("dataset_size"),
            result.get("n_nodes"),
        )
        return
    upsert_timing_result(sheet_id, result)


# Pivot table layout on Complexity_* tabs (QUERY spill from A1).
_PIVOT_DATASET_COLS = ["B", "C", "D", "E", "F", "G"]
_PIVOT_DATASET_LABELS = ["5000", "10000", "20000", "30000", "40000", "50000"]
_PIVOT_MIN_COLS = ["H", "I", "J", "K", "L", "M"]
_PIVOT_MAX_DATA_ROW = 15  # header row 1 + up to 14 N values

# Default experiment_id per complexity tab (paper replication grids).
_DEFAULT_COMPLEXITY_EXPERIMENTS: dict[str, str] = {
    "low": "paper_replication_low_compute_only",
    "medium": "paper_replication_medium_compute_only",
}


def complexity_min_marker_formula(*, data_col: str, row: int) -> str:
    """Mark Y (time) at the row where column ``data_col`` attains its minimum."""
    end = _PIVOT_MAX_DATA_ROW
    data_range = f"{data_col}$2:{data_col}${end}"
    node_range = f"A$2:A${end}"
    return (
        f"=IF({data_col}{row}=MIN(FILTER({data_range}, {node_range}<>\"\")), "
        f"{data_col}{row}, NA())"
    )


def complexity_pivot_query_formula(
    *,
    complexity: str,
    experiment_id: str | None = None,
    mode: str | None = "compute_only",
    metric: str = "wall_clock",
    succeeded_only: bool = True,
) -> str:
    """
    Build a QUERY formula for Complexity_* analysis tabs.

    metric:
      - wall_clock → Z (s3 + cluster_init + cluster_parallel; paper T(N,D) proxy)
      - total_pipeline → O (s3 + cluster_parallel; compute_only omits init)
      - computation → L (slowest-shard runtime)
      - cluster_parallel → Y (array wall clock)
    """
    col = _METRIC_COLUMNS.get(metric, "Z")
    clauses = [f"F = '{complexity}'"]
    if mode:
        clauses.append(f"C = '{mode}'")
    if experiment_id:
        clauses.append(f"B = '{experiment_id}'")
    if succeeded_only:
        clauses.append("W = 'SUCCEEDED'")
    where = " AND ".join(clauses)
    return (
        f"=QUERY({_RESULTS_QUERY_RANGE}, "
        f'"SELECT E, AVG({col}) WHERE {where} GROUP BY E PIVOT D LABEL E \'Nodes\'", 1)'
    )


def _complexity_experiment_filter(
    complexity: str,
    *,
    experiment_id: str | None,
) -> str | None:
    """Resolve experiment filter: explicit arg > env > per-tab paper default."""
    if experiment_id:
        return experiment_id
    env = os.getenv("SHEETS_EXPERIMENT_FILTER", "").strip()
    if env:
        return env
    return _DEFAULT_COMPLEXITY_EXPERIMENTS.get(complexity)


def _update_complexity_min_markers(ws: Any) -> None:
    """Rewrite H1:M* min-marker columns aligned to pivot dataset cols B:G."""
    header_row = [f"Min {label}" for label in _PIVOT_DATASET_LABELS]
    ws.update("H1:M1", [header_row])

    updates: list[dict[str, str]] = []
    for row in range(2, _PIVOT_MAX_DATA_ROW + 1):
        for min_col, data_col in zip(_PIVOT_MIN_COLS, _PIVOT_DATASET_COLS):
            cell = f"{min_col}{row}"
            updates.append(
                {
                    "range": cell,
                    "values": [[complexity_min_marker_formula(data_col=data_col, row=row)]],
                }
            )
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")


def update_complexity_analysis_tabs(
    sheet_id: str,
    *,
    experiment_id: str | None = None,
    metric: str = "wall_clock",
) -> None:
    """
    Refresh Complexity_Low / Complexity_Medium pivot tables (A1 layout only).

    A1: QUERY pivot (default wall_clock col W; SUCCEEDED compute_only rows).
    H1:M*: min-marker scatter helpers for connected charts.

    Defaults to paper_replication_*_compute_only per tab unless experiment_id or
    SHEETS_EXPERIMENT_FILTER is set.
    """
    gc = _get_client()
    sh = gc.open_by_key(sheet_id)

    tab_specs = [
        ("Complexity_Low", "low"),
        ("Complexity_Medium", "medium"),
    ]
    for title, complexity in tab_specs:
        try:
            ws = sh.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=title, rows=200, cols=20)

        exp_filter = _complexity_experiment_filter(complexity, experiment_id=experiment_id)
        formula = complexity_pivot_query_formula(
            complexity=complexity,
            experiment_id=exp_filter,
            mode="compute_only",
            metric=metric,
            succeeded_only=True,
        )
        ws.update_acell("A1", formula)
        _update_complexity_min_markers(ws)
        logger.info(
            "Updated {} pivot ({}, compute_only, exp={})",
            title,
            metric,
            exp_filter or "ALL",
        )
    logger.info("Complexity analysis tabs refreshed on sheet {}", sheet_id)


def sync_results_and_complexity_tabs(
    sheet_id: str,
    *,
    experiment_id: str | None = None,
    metric: str = "wall_clock",
) -> dict[str, Any]:
    """Backfill V/W, dedupe paper compute rows in place, refresh Complexity A1 pivots."""
    backfilled = backfill_results_derived_metrics(sheet_id)
    dedupe_stats = dedupe_paper_compute_results(sheet_id)
    backfill_results_derived_metrics(sheet_id)
    update_complexity_analysis_tabs(sheet_id, experiment_id=experiment_id, metric=metric)
    return {"backfilled_rows": backfilled, **dedupe_stats}


def read_results_rows(sheet_id: str, *, limit: int = 5000) -> list[list[str]]:
    """Return all values from Results (including header). For inspection scripts."""
    ws = get_sheet(sheet_id, "Results")
    return ws.get_all_values()[: limit + 1]


def summarize_results_rows(rows: list[list[str]]) -> dict[str, Any]:
    """Aggregate counts by experiment_id, mode, complexity from Results sheet rows."""
    if not rows or len(rows) < 2:
        return {"row_count": 0, "by_experiment": {}}
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    by_exp: dict[str, dict[str, int]] = {}
    for row in rows[1:]:
        if len(row) <= max(idx.get("Experiment ID", 1), idx.get("Mode", 2)):
            continue
        exp = row[idx.get("Experiment ID", 1)]
        mode = row[idx.get("Mode", 2)]
        comp = row[idx.get("SMILES Complexity", 5)] if len(row) > 5 else ""
        key = f"{exp}|{mode}|{comp}"
        by_exp[key] = by_exp.get(key, 0) + 1
    return {"row_count": len(rows) - 1, "by_experiment": by_exp, "headers": header}


def update_phase_summary(sheet_id: str) -> None:
    """
    Ensure a 'Phase Summary' worksheet exists with formulas that compute
    mean and stddev per (D, N) combination for each phase.

    We write a static header and a formula row based on QUERY; formulas
    will auto-expand as new rows are appended to 'Results'.
    """
    gc = _get_client()
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Phase Summary")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Phase Summary", rows=1000, cols=20)

    headers = [
        "Dataset Size (D)",
        "Nodes (N)",
        "Mode",
        "Mean Computation (s)",
        "StdDev Computation (s)",
        "Mean Upload (s)",
        "StdDev Upload (s)",
        "Mean Total Pipeline (s)",
        "StdDev Total Pipeline (s)",
    ]
    ws.update("A1", [headers])

    # Use entire columns from Results to stay up to date.
    formula = (
        '=QUERY('
        "Results!D2:O,"
        '"select D, E, C, '
        'avg(L), stdev(L), '
        'avg(I), stdev(I), '
        'avg(O), stdev(O) '
        'group by D, E, C", 0)'
    )
    ws.update_acell("A2", formula)


def update_timing_breakdown_chart_data(sheet_id: str) -> None:
    """
    Write/update a 'Timing Breakdown' worksheet with per-run phase percentages.

    Columns: D | N | Mode | Upload% | Compute% | Overhead% | Total
    """
    gc = _get_client()
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Timing Breakdown")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Timing Breakdown", rows=1000, cols=10)

    headers = [
        "Dataset Size (D)",
        "Nodes (N)",
        "Mode",
        "Upload%",
        "Compute%",
        "Overhead%",
        "Total Pipeline (s)",
    ]
    ws.update("A1", [headers])

    # Derive percentages from Results; reference whole columns.
    # I: S3 Upload (s), L: Computation (s), M: Sync Overhead (s), O: Total Pipeline (s)
    formula = (
        '=ARRAYFORMULA(IF(Results!D2:D="","",'
        " {Results!D2:D, Results!E2:E, Results!C2:C, "
        "  IF(Results!O2:O=0,0,Results!I2:I/Results!O2:O*100), "
        "  IF(Results!O2:O=0,0,Results!L2:L/Results!O2:O*100), "
        "  IF(Results!O2:O=0,0,Results!M2:M/Results!O2:O*100), "
        "  Results!O2:O} ))"
    )
    ws.update_acell("A2", formula)
    logger.info("Updated 'Timing Breakdown' worksheet formulas.")


def append_estimate_row_for_config(
    sheet_id: str,
    summary: Dict[str, Any],
    cfg: Dict[str, Any],
    est: Dict[str, Any],
    *,
    ws: Any | None = None,
) -> None:
    """
    Append ONE row to 'Estimates' for a single (D, N) config.

    If ``ws`` is provided (opened ``Estimates`` worksheet), it is reused to avoid
    repeated spreadsheet open/read calls that trigger Google Sheets 429 quotas.
    The caller must ensure the header row exists when passing ``ws``.
    """
    if ws is None:
        ws = get_sheet(sheet_id, "Estimates")
        if not ws.row_values(1):
            ws.update("A1", [ESTIMATES_HEADERS])

    # Run-level metadata
    timestamp = datetime.utcnow().isoformat()
    experiment_name = summary.get("experiment_name", "")
    config_path = summary.get("config_path", "")
    pricing_mode = "SPOT" if summary.get("use_spot", True) else "ON-DEMAND"

    # Shape of the run
    n_jobs = summary.get("n_jobs", "")
    n_dataset_sizes = summary.get("n_dataset_sizes", "")
    n_node_configs = summary.get("n_node_configs", "")
    n_replicas = summary.get("n_replicas", "")
    total_time_sec = summary.get("total_time_sec", "")
    total_time_min = summary.get("total_time_min", "")
    total_time_hours = summary.get("total_time_hours", "")
    total_cost_usd = summary.get("total_cost_usd", "")
    total_cost_spot = summary.get("total_cost_spot_usd", "")
    total_cost_ondemand = summary.get("total_cost_ondemand_usd", "")

    # This config
    D = int(est["dataset_size"])
    N = int(est["n_nodes"])

    level = cfg.get("smiles_complexity", "medium")
    level_map = {"low": 0.85, "medium": 1.0, "high": 1.3}
    len_map = {"low": 30, "medium": 57, "high": 90}
    complexity_score = level_map.get(level, 1.0)
    expected_len = len_map.get(level, 57)

    # Prefer true pre-SMILES compound length if available; fall back to SMILES length.
    avg_chem_len = est.get("compound_avg_length", est.get("smiles_avg_length", ""))
    dataset_size_mb = est.get("dataset_size_mb", "")
    s3 = est.get("s3_upload_sec", "")
    cluster = est.get("cluster_init_sec", "")
    sched = est.get("scheduling_sec", "")
    comp = est.get("computation_sec", "")
    sync = est.get("sync_overhead_sec", "")
    result_up = est.get("result_upload_sec", "")
    total_pipe = est.get("total_pipeline_sec", "")
    cost = est.get("estimated_cost_usd", "")
    cost_spot = est.get("estimated_cost_spot_usd", "")
    cost_od = est.get("estimated_cost_ondemand_usd", "")

    n_star = summary.get("optimal_nodes", {}).get(D, "")

    row = [
        timestamp,
        experiment_name,
        config_path,
        n_jobs,
        n_dataset_sizes,
        n_node_configs,
        n_replicas,
        total_time_sec,
        total_time_min,
        total_time_hours,
        total_cost_usd,
        total_cost_spot,
        total_cost_ondemand,
        pricing_mode,
        D,
        N,
        level,
        complexity_score,
        avg_chem_len,
        expected_len,
        dataset_size_mb,
        s3,
        cluster,
        sched,
        comp,
        sync,
        result_up,
        total_pipe,
        cost,
        cost_spot,
        cost_od,
        n_star,
    ]
    ws.append_row(row)
    logger.info(
        "Estimator per-config row appended for experiment_name={} D={} N={}",
        experiment_name,
        D,
        N,
    )


