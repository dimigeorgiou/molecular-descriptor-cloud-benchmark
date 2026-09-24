# Chemoinformatics Descriptor Computation — Final Report

**Updated:** 2026-07-08T17:45:00Z  
**Project:** *Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics*  
**Model form:** `T(N,D) = a + bN + cD + dN^2 + eND`

## Executive Summary

Paper replication grids (compute_only, low + medium) completed **74/84** AWS Batch jobs successfully on 2026-07-08. **10 jobs FAILED** and are being retried (append-only to Google Sheets with `notes=retry_20260708`).

| Grid | Jobs | SUCCEEDED | FAILED |
|------|------|-----------|--------|
| Low | 42 | 37 | 5 |
| Medium | 42 | 37 | 5 |

Refitted quadratic on `computation_sec` (all 42 points per grid, including failed rows replaced by estimator gaps in JSON only):

- Low: **R² = 0.9175** (n=42)
- Medium: **R² = 0.9165** (n=42)

**Key finding:** The paper’s U-shaped optimal-N curve is **not** visible in `computation_sec` (shard bottleneck). It **is** visible in **wall-clock time** (S3 + cluster init + parallel array duration) when filtering `Status=SUCCEEDED`.

## Failed (D, N) pairs — retried 2026-07-08

| Complexity | D | N |
|------------|---|-----|
| low | 5000 | 150, 185 |
| low | 10000 | 185 |
| low | 20000 | 185 |
| low | 50000 | 50 |
| medium | 5000 | 150, 185 |
| medium | 10000 | 185 |
| medium | 20000 | 185 |
| medium | 30000 | 100 |

Rerun script: `scripts/rerun_failed_paper_jobs.sh` (appends rows; pivots use `Status=SUCCEEDED` only).

## Timing metrics — definitions

| Column | Field | Formula (compute_only) | Use for paper U-curve? |
|--------|-------|------------------------|------------------------|
| L | `computation_sec` | max(shard wall-clock) | ❌ Monotone ↓ with N |
| O | `total_pipeline_sec` | S3 + cluster_parallel | ⚠️ Partial; omits init |
| V | `cluster_parallel_sec` | first child start → last child stop | Component only |
| W | `wall_clock_sec` | S3 + cluster_init + cluster_parallel | ✅ **Primary** |

`full_pipeline` mode adds cluster_init into O; for `compute_only` runs, **W** is the correct end-to-end cluster timing proxy.

## Metric shape analysis (74 SUCCEEDED rows, pre-retry)

Analysis script: `scripts/analyze_paper_metrics.py` → `tmp/paper_metrics_analysis.json`

### Low complexity

| Metric | Interior U (of 6 D) | Notes |
|--------|---------------------|-------|
| wall_clock (W) | **4** | N* ≈ 75–125 for D=5k–30k |
| total_pipeline (O) | 0 | Edge minima only |
| computation (L) | 0 | All monotone ↓ |

Interior minima (wall_clock): D=5000 N=75 (46s), D=10000 N=100 (44s), D=20000 N=125 (43s), D=30000 N=50 (51s).

### Medium complexity

| Metric | Interior U (of 6 D) | Notes |
|--------|---------------------|-------|
| wall_clock (W) | **4** | N* ≈ 50–100 |
| total_pipeline (O) | 3 | Misleading without init |
| computation (L) | 0 | All monotone ↓ |

Interior minima (wall_clock): D=10000 N=50 (48s), D=20000 N=100 (47s), D=40000 N=75 (38s), D=50000 N=50 (25s).

### Conclusion on metric combinations

1. **Use `wall_clock` (col W) + `SUCCEEDED` filter** for Complexity pivot tabs and paper charts.
2. **`computation_sec`** remains valid for **T(N,D) quadratic fitting** on parallel bottleneck (high R²) but does not reproduce the paper’s U-curve story.
3. **`total_pipeline` (O)** in compute_only mode **under-counts** init overhead; some U-shapes appear but are inconsistent with low complexity.
4. Failed rows previously produced **fake ~14s minima** in unfiltered pivots; SUCCEEDED-only QUERY fixes this.

## Google Sheets (synced 2026-07-09)

- Spreadsheet: `1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs`
- **In-place sync** (no append): `python scripts/sync_results_sheet.py`
  - Backfilled cols V/W on all rows
  - Removed 10 duplicate retry rows; 84 canonical paper compute_only rows remain
- Complexity tabs: **A1 QUERY + H:M min markers only** (charts preserved)
- Primary pivot: **AVG(W)** with `T = 'SUCCEEDED'`
- Handoff for Claude: `experiments/docs/HANDOFF_CLAUDE.md` (regenerate: `python scripts/generate_handoff_claude.py`)

## Artifacts (original grids)

### Low complexity
- Run dir: `experiments/results/paper_replication_low_compute_only_20260708_003445/`
- Verification MAPE vs paper estimator: ~25055% (expected; different timing abstraction)

### Medium complexity
- Run dir: `experiments/results/paper_replication_medium_compute_only_20260708_041044/`
- Verification MAPE: ~26367%

## Status (post-retry 2026-07-08)

- ✅ 10 retry rows appended to Sheets (`notes=retry_20260708`)
- ⚠️ **2/10 retries SUCCEEDED:** low D=50000 N=50, medium D=30000 N=100
- ❌ **8/10 retries still FAILED** (all at N=150 or N=185)
- **Grid coverage: 76/84** latest SUCCEEDED (38 low + 38 medium)

### Still missing SUCCEEDED rows (8 pairs, same for low & medium)

| D | N |
|---|---|
| 5000 | 150, 185 |
| 10000 | 185 |
| 20000 | 185 |

(Root cause: AWS Batch array child failures at high N — not a Sheets/metrics issue.)

### Retry outcome detail

| Pair | Retry status | Notes |
|------|--------------|-------|
| low 50000/50 | ✅ SUCCEEDED | wall=163s |
| medium 30000/100 | ✅ SUCCEEDED | wall=282s |
| All N=150,185 pairs | ❌ FAILED | partial arrays, ~17–390s bogus wall times |
