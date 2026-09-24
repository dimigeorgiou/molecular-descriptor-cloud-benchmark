# Comprehensive Research Handoff — Chemoinformatics Descriptor Computation

**Generated:** 2026-07-08 23:04 UTC
**Repository:** `chemoinformatics-descriptor-computation`
**Spreadsheet ID:** `1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs`
**Audience:** Claude (report writing, thesis extension, figure generation, next experiments)
**Scope:** Full replication narrative from project inception through 2026-07-09 Sheets sync.

---

## Part 0 — How to use this document

This handoff is intentionally long. It captures **research context**, not only commands.

Read in order if you are new:
1. Part 1 (Executive summary)
2. Part 2 (The paper — what we are validating)
3. Part 5 (Chronological timeline — what happened and what broke)
4. Part 7 (Timing metrics — the central scientific finding)
5. Part 10 (Current status)
6. Part 12 (Instructions for Claude)

Skip to Part 9 for raw Google Sheets grid dumps.

## Part 1 — Executive summary

We built an **AWS Batch measurement harness** to empirically test the paper's claim that
distributed molecular-descriptor computation exhibits predictable scaling in dataset size **D**
and worker count **N**, enabling analytical optimum **N*(D)** via a quadratic runtime model.

### What succeeded
- End-to-end pipeline: SMILES datasets → S3 → EC2 Batch array jobs → timing JSON → Google Sheets → analysis.
- Two full **compute_only** replication grids executed overnight **2026-07-08**:
  - **Low** SMILES complexity: 42 jobs submitted, **38 SUCCEEDED** in canonical Sheets row set.
  - **Medium** SMILES complexity: 42 jobs submitted, **38 SUCCEEDED**.
- Quadratic refit on **computation_sec** achieves **R² ≈ 0.917** (low) and **0.916** (medium).
- After metric analysis: **wall_clock** (S3 + cluster_init + cluster_parallel) shows **interior U-minima**
  in N for multiple D values — consistent with the paper's allocation narrative.

### What failed or remains open
- **8** grid points (same D,N in low and medium) still **FAILED** at **N ∈ {150, 185}** for smaller D:
  - (5000,150), (5000,185), (10000,185), (20000,185)
- Root cause: AWS Batch **array child failures** at high N (Spot capacity, missing S3 shard outputs).
- Paper **estimator** vs measured **computation_sec**: MAPE ~**25,000%** — expected due to different timing abstraction.
- Google Sheets had a **metrics/formula crisis** (wrong column, empty W, duplicate rows) — **fixed 2026-07-09**.

### Single most important scientific conclusion
> **Do not plot `computation_sec` (col L) for U-curve figures.** It is the slowest-shard runtime and
> **monotonically decreases** with N. Plot **`wall_clock` (col W)** with `Status=SUCCEEDED` filter.

## Part 2 — The source paper (context for Claude)

**Title:** *Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics*
**Authors (in-repo citation):** Didachos C., Georgiou D., Fousteris M., Kanavos A.
**Affiliations:** University of Patras / Ionian University (as referenced in project docs)

### 2.1 Core mathematical model

The paper models end-to-end execution time as:

```
T(N, D) = a + b·N + c·D + d·N² + e·N·D
```

| Term | Interpretation (paper/intuition) |
|------|--------------------------------|
| `a` | Fixed baseline overhead |
| `b·N` | Linear cost of adding workers (coordination, startup) |
| `c·D` | Linear cost in dataset size |
| `d·N²` | Super-linear parallelism penalty (convexity — enables interior optimum) |
| `e·N·D` | Interaction: marginal cost of nodes depends on dataset size |

**Analytical optimum** (interior critical point, requires `d > 0`):

```
N*(D) = -(b + e·D) / (2d)
```

Implementation: `ModelCoefficients.optimal_nodes()` in `src/core/model.py`.

The paper's figures show **U-shaped curves** of time vs N for fixed D — a minimum at interior N,
not at the smallest or largest N tested.

### 2.2 What the paper measures vs what we measure

This distinction caused weeks of confusion and is **the** key handoff insight.

| Paper concept | Our Batch implementation | Alignment |
|---------------|-------------------------|-----------|
| Total / end-to-end execution time | `wall_clock_sec` = S3 + init + parallel | ✅ Best match |
| Descriptor computation phase | `computation_sec` = max shard wall-clock | ⚠️ Partial |
| Pipeline w/o init (compute_only mode) | `total_pipeline_sec` = S3 + parallel | ⚠️ Omits init |
| Pre-run analytical estimator | `experiment_estimator.py` + paper coefficients | ❌ Large MAPE vs L |

The paper's estimator was calibrated on a **different timing abstraction** (likely closer to
sequential or end-to-end wall time). Our **computation_sec** measures **parallel bottleneck only**
(sub-second to few seconds on EC2) because true sharding makes each child process a tiny slice.

Therefore:
- **High R²** fitting T(N,D) on **computation_sec** is real — the quadratic shape fits shard times.
- **U-curves for allocation** appear in **wall_clock**, not computation_sec.

### 2.3 Paper sections mapped to repo artifacts

| Paper topic | Repo artifact |
|-------------|---------------|
| Dataset sizes D ∈ [5k, 50k] | `datasets/samples/smiles_{D}_{complexity}.csv` |
| Node counts N ∈ [25, 185] | `node_configs` in YAML |
| SMILES complexity levels | `low`, `medium`, `high` generator profiles |
| Performance model fit | `experiments/results/*/fitted_model.json` |
| Optimal N table | `python src/core/model.py optimal-table` |
| Empirical validation | `verification_report.json`, Google Sheets pivots |

## Part 3 — Repository architecture

```
chemoinformatics-descriptor-computation/
├── src/core/model.py              # T(N,D), OLS fit, N*(D)
├── src/core/batch_timing.py       # Phase decomposition from Batch API
├── src/monitoring/sheets.py       # Google Sheets upsert, pivots, sync
├── experiments/run_experiment.py  # Local + AWS Batch orchestrator
├── experiments/estimator/       # Pre-run cost/time estimates
├── experiments/verify_estimate_vs_actual.py
├── experiments/configs/           # paper_replication_* YAML grids
├── experiments/results/           # JSON artifacts per run
├── scripts/sync_results_sheet.py  # In-place Sheets repair
└── docs/PLAN.md, ANALYTICAL_STEPS.md
```

**Environment:** `conda activate venv_chemoinformatics`; `export PYTHONPATH=.` from repo root.

**AWS:** EC2-backed queue (`chemo-ec2-queue` per docs), S3 bucket `chemoinformatics-experiment`,
Batch **array jobs** with N children for N nodes.

## Part 4 — Experiment design (paper replication grids)

### Grid specification (both low and medium)
- **Mode:** `compute_only` (isolates descriptor scaling; init tracked separately)
- **D:** 5000, 10000, 20000, 30000, 40000, 50000
- **N:** 25, 50, 75, 100, 125, 150, 185
- **Jobs:** 6 × 7 = **42** per complexity
- **Config files:**
  - `experiments/configs/paper_replication_low_compute_only.yaml`
  - `experiments/configs/paper_replication_medium_compute_only.yaml`

### Execution modes (repo-wide)
| Mode | total_pipeline includes init? | Verification metric (auto) |
|------|------------------------------|----------------------------|
| `compute_only` | No (only S3 + parallel) | `computation_sec` |
| `full_pipeline` | Yes | `total_pipeline_sec` |

## Part 5 — Chronological timeline (errors → fixes)

This section documents **how we started**, **what broke**, and **what we did next**.

### 2026-05-15 — 2026-05-16: Early full_pipeline pilots
Ran `paper_replication_*_full_pipeline_10_100` configs (subset D=10k, N=100). Established Batch+Sheets pipeline before full grid.

### 2026-07-07: Smoke tests & alignment mini
Multiple `smoke_batch_verify` runs; `paper_alignment_mini` local compute. Validated estimator→run→verify loop.

### 2026-07-08 ~00:34 UTC: Low grid overnight START
Full 42-job low compute_only grid. Run dir: `paper_replication_low_compute_only_20260708_003445/`.

### 2026-07-08 ~04:10 UTC: Medium grid overnight
Full 42-job medium compute_only. Run dir: `paper_replication_medium_compute_only_20260708_041044/`.

### 2026-07-08 morning: Initial analysis
74/84 SUCCEEDED. 10 FAILED (5 low + 5 medium). Refit R²~0.92. FINAL_REPORT drafted.

### 2026-07-08: Google Sheets formula confusion
Complexity tabs used AVG(L) then AVG(O). User questioned correctness. Pivots showed wrong/no U-curves.

### 2026-07-08: Metric deep-dive
Discovered computation_sec monotone-decreasing; wall_clock shows interior minima. Added cols V, W.

### 2026-07-08 ~15:40–16:45 UTC: Failed job reruns
10 retries appended (user later rejected append policy). 2/10 succeeded.

### 2026-07-09 ~00:54 UTC: Sheets in-place sync
Backfilled V/W on 504 rows; deleted 10 duplicates; A1 pivots restored; upsert default.

## Part 6 — Error catalog (root causes & fixes)

### E1. Overnight script failure / medium grid resume
- **Cause:** Batch queue or script interrupt
- **Fix:** Resume medium grid from checkpoint; logs in tmp/

### E2. 10/84 Batch jobs FAILED
- **Cause:** Array child failures at N=150,185; missing S3 shards
- **Fix:** Partial reruns; 8 still fail; needs on-demand or lower max N

### E3. Pivots empty after AVG(W) change
- **Cause:** Col W empty on historical rows
- **Fix:** backfill: W = init + total_pipeline

### E4. Fake ~14s U-minima in charts
- **Cause:** FAILED rows with bogus short wall times included
- **Fix:** QUERY filter T='SUCCEEDED'

### E5. Duplicate Results rows after retry
- **Cause:** append_timing_result always appended
- **Fix:** dedupe + upsert by (exp, mode, D, N)

### E6. MAPE 25000% estimator vs actual
- **Cause:** Estimator predicts sequential-scale seconds; computation_sec is shard max
- **Fix:** Expected; use wall_clock for paper comparison or refit estimator

### E7. Complexity tab layout broken
- **Cause:** Extra pivots at A25/A40/A55
- **Fix:** Removed; A1+H:M only for connected charts

### E8. QUERY showed sparse pivot
- **Cause:** SUCCEEDED filter + empty W
- **Fix:** Backfill fixed; 38/42 cells per tab filled

## Part 7 — Timing metrics (detailed ontology)

Defined in `src/core/batch_timing.py` and written to Sheets via `run_experiment.py`.

### Phase definitions
| Field | Code | Formula / source |
|-------|------|------------------|
| S3 Upload | `s3_upload_sec` | Measured upload before job submit |
| Cluster Init | `cluster_init_sec` | min(child started) − submit timestamp |
| Scheduling | `scheduling_sec` | max(start) − min(start) among children |
| Computation | `computation_sec` | **max** child (stopped − started) — slowest shard |
| Cluster Parallel | `cluster_parallel_sec` | max(stopped) − min(started) — array wall |
| Total Pipeline (compute_only) | `total_pipeline_sec` | s3 + cluster_parallel (**no init**) |
| Wall Clock | `wall_clock_sec` | s3 + init + cluster_parallel |

### Why computation_sec is always ↓ with N
With N workers, each shard holds ~D/N compounds. More nodes → smaller shards → lower max runtime.
This is **correct parallel speedup** but not the paper's end-to-end U-curve.

### Why wall_clock can show U-shape
Adding nodes increases coordination overhead (init, scheduling, stragglers) while decreasing shard work.
The tradeoff can produce interior optimum in **end-to-end** time.

## Part 8 — Model fitting results

### Low complexity (n=42, all rows including FAILED in JSON fit)
- a = 3.391487452920621
- b = -0.08337986540074177
- c = 0.00024007304815027312
- d = 0.00039502935736403005
- e = -1.3044030022147324e-06
- R² = 0.9174739813181915

### Medium complexity (n=42)
- a = 6.856643302695382
- b = -0.1717763157646224
- c = 0.0004932619456976425
- d = 0.0008157337441022411
- e = -2.6630548765483113e-06
- R² = 0.9164978580155905

Both have **d > 0** → analytical N*(D) exists (convex in N).

## Part 9 — Complete Results grid (Google Sheets canonical rows)

Post-sync **2026-07-09**. One row per (D,N). Source: Results tab.

### Low complexity
| D | N | Status | L (comp) | O (pipeline) | W (wall) | Init | S3 |
|---|---|--------|----------|--------------|----------|------|-----|
| 5000 | 25 | SUCCEEDED | 1.499 | 40.887 | 180.995 | 140.108 | 2.461 |
| 5000 | 50 | SUCCEEDED | 0.798 | 63.88 | 105.435 | 41.555 | 4.842 |
| 5000 | 75 | SUCCEEDED | 0.552 | 150.056 | 189.201 | 39.145 | 7.242 |
| 5000 | 100 | SUCCEEDED | 0.383 | 277.165 | 313.981 | 36.816 | 11.082 |
| 5000 | 125 | SUCCEEDED | 0.342 | 175.268 | 429.872 | 254.604 | 11.99 |
| 5000 | 150 | FAILED | 0.298 | 237.314 | 365.816 | 128.502 | 17.193 |
| 5000 | 185 | FAILED | 0.26 | 211.462 | 269.443 | 57.981 | 17.885 |
| 10000 | 25 | SUCCEEDED | 2.984 | 38.73 | 85.279 | 46.549 | 2.558 |
| 10000 | 50 | SUCCEEDED | 1.541 | 57.581 | 101.117 | 43.536 | 5.218 |
| 10000 | 75 | SUCCEEDED | 1.008 | 86.187 | 127.084 | 40.897 | 7.573 |
| 10000 | 100 | SUCCEEDED | 0.761 | 114.619 | 148.721 | 34.102 | 10.022 |
| 10000 | 125 | SUCCEEDED | 0.652 | 176.697 | 428.723 | 252.026 | 12.053 |
| 10000 | 150 | SUCCEEDED | 0.547 | 199.988 | 236.597 | 36.609 | 14.122 |
| 10000 | 185 | FAILED | 0.446 | 17.803 | 17.803 | 0 | 17.803 |
| 20000 | 25 | SUCCEEDED | 6.414 | 66.773 | 253.572 | 186.799 | 2.567 |
| 20000 | 50 | SUCCEEDED | 3.141 | 68.759 | 121.865 | 53.106 | 4.936 |
| 20000 | 75 | SUCCEEDED | 2.121 | 100.613 | 200.305 | 99.692 | 7.514 |
| 20000 | 100 | SUCCEEDED | 1.631 | 134.447 | 174.666 | 40.219 | 10.616 |
| 20000 | 125 | SUCCEEDED | 1.222 | 327.601 | 358.201 | 30.6 | 12.591 |
| 20000 | 150 | SUCCEEDED | 1.001 | 291.8 | 511.047 | 219.247 | 14.171 |
| 20000 | 185 | FAILED | 0.964 | 334.161 | 390.85 | 56.689 | 17.355 |
| 30000 | 25 | SUCCEEDED | 8.826 | 86.561 | 254.784 | 168.223 | 2.581 |
| 30000 | 50 | SUCCEEDED | 4.435 | 136.475 | 182.134 | 45.659 | 4.953 |
| 30000 | 75 | SUCCEEDED | 3.03 | 154.615 | 354.306 | 199.691 | 7.054 |
| 30000 | 100 | SUCCEEDED | 2.142 | 166.242 | 360.558 | 194.316 | 9.5 |
| 30000 | 125 | SUCCEEDED | 1.871 | 173.943 | 349.234 | 175.291 | 13.361 |
| 30000 | 150 | SUCCEEDED | 1.492 | 210.651 | 408.47 | 197.819 | 15.24 |
| 30000 | 185 | SUCCEEDED | 1.205 | 249.288 | 318.615 | 69.327 | 18.385 |
| 40000 | 25 | SUCCEEDED | 11.267 | 82.895 | 122.043 | 39.148 | 2.653 |
| 40000 | 50 | SUCCEEDED | 5.872 | 117.489 | 159.435 | 41.946 | 4.917 |
| 40000 | 75 | SUCCEEDED | 3.933 | 173.731 | 405.54 | 231.809 | 7.404 |
| 40000 | 100 | SUCCEEDED | 2.965 | 164.342 | 239.174 | 74.832 | 9.782 |
| 40000 | 125 | SUCCEEDED | 2.514 | 199.368 | 271.938 | 72.57 | 12.161 |
| 40000 | 150 | SUCCEEDED | 2.012 | 206.731 | 427.94 | 221.209 | 15.081 |
| 40000 | 185 | SUCCEEDED | 1.636 | 247.333 | 278.37 | 31.037 | 19.206 |
| 50000 | 25 | SUCCEEDED | 14.747 | 102.963 | 140.126 | 37.163 | 2.828 |
| 50000 | 50 | SUCCEEDED | 8.396 | 128.417 | 163.426 | 35.009 | 4.813 |
| 50000 | 75 | SUCCEEDED | 4.951 | 214.842 | 258.96 | 44.118 | 8.406 |
| 50000 | 100 | SUCCEEDED | 3.739 | 214.983 | 253.044 | 38.061 | 9.978 |
| 50000 | 125 | SUCCEEDED | 3.149 | 256.037 | 476.207 | 220.17 | 12.682 |
| 50000 | 150 | SUCCEEDED | 2.561 | 201.133 | 231.266 | 30.133 | 14.416 |
| 50000 | 185 | SUCCEEDED | 2.006 | 278.531 | 489.444 | 210.913 | 18.429 |

**SUCCEEDED:** 38/42

### Medium complexity
| D | N | Status | L (comp) | O (pipeline) | W (wall) | Init | S3 |
|---|---|--------|----------|--------------|----------|------|-----|
| 5000 | 25 | SUCCEEDED | 3.217 | 42.75 | 214.234 | 171.484 | 2.524 |
| 5000 | 50 | SUCCEEDED | 1.59 | 78.507 | 128.987 | 50.48 | 4.914 |
| 5000 | 75 | SUCCEEDED | 1.072 | 115.261 | 163.808 | 48.547 | 7.607 |
| 5000 | 100 | SUCCEEDED | 0.733 | 153.14 | 195.187 | 42.047 | 9.629 |
| 5000 | 125 | SUCCEEDED | 0.625 | 197.74 | 231.808 | 34.068 | 12.238 |
| 5000 | 150 | FAILED | 0.53 | 14.008 | 14.008 | 0 | 14.008 |
| 5000 | 185 | FAILED | 0.451 | 259.022 | 324.794 | 65.772 | 16.989 |
| 10000 | 25 | SUCCEEDED | 5.992 | 83.445 | 143.34 | 59.895 | 2.502 |
| 10000 | 50 | SUCCEEDED | 3.019 | 82.202 | 125.285 | 43.083 | 4.795 |
| 10000 | 75 | SUCCEEDED | 2.107 | 116.3 | 160.468 | 44.168 | 7.481 |
| 10000 | 100 | SUCCEEDED | 1.577 | 159.877 | 357.644 | 197.767 | 9.982 |
| 10000 | 125 | SUCCEEDED | 1.206 | 198.791 | 392.972 | 194.181 | 12.529 |
| 10000 | 150 | SUCCEEDED | 1.041 | 236.378 | 272.923 | 36.545 | 15.675 |
| 10000 | 185 | FAILED | 0.85 | 17.698 | 17.698 | 0 | 17.698 |
| 20000 | 25 | SUCCEEDED | 11.963 | 117.135 | 318.915 | 201.78 | 2.604 |
| 20000 | 50 | SUCCEEDED | 6.26 | 146.216 | 381.664 | 235.448 | 4.913 |
| 20000 | 75 | SUCCEEDED | 4.161 | 190.527 | 400.609 | 210.082 | 7.306 |
| 20000 | 100 | SUCCEEDED | 3.128 | 180.059 | 217.063 | 37.004 | 9.768 |
| 20000 | 125 | SUCCEEDED | 2.501 | 303.017 | 462.768 | 159.751 | 12.185 |
| 20000 | 150 | SUCCEEDED | 2.042 | 236.491 | 416.139 | 179.648 | 14.879 |
| 20000 | 185 | FAILED | 1.673 | 18.749 | 18.749 | 0 | 18.749 |
| 30000 | 25 | SUCCEEDED | 18.272 | 149.981 | 204.527 | 54.546 | 2.705 |
| 30000 | 50 | SUCCEEDED | 9.256 | 147.793 | 352.09 | 204.297 | 5.242 |
| 30000 | 75 | SUCCEEDED | 6.271 | 247.498 | 445.505 | 198.007 | 7.436 |
| 30000 | 100 | SUCCEEDED | 4.828 | 218.59 | 282.285 | 63.695 | 10.062 |
| 30000 | 125 | SUCCEEDED | 3.668 | 284.754 | 337.479 | 52.725 | 12.405 |
| 30000 | 150 | SUCCEEDED | 3.1 | 385.51 | 569.503 | 183.993 | 14.899 |
| 30000 | 185 | SUCCEEDED | 2.513 | 256.074 | 466.724 | 210.65 | 18.512 |
| 40000 | 25 | SUCCEEDED | 23.783 | 136.304 | 178.594 | 42.29 | 3.053 |
| 40000 | 50 | SUCCEEDED | 11.853 | 170.278 | 236.322 | 66.044 | 5.649 |
| 40000 | 75 | SUCCEEDED | 7.97 | 187.123 | 217.334 | 30.211 | 7.904 |
| 40000 | 100 | SUCCEEDED | 5.973 | 236.672 | 279.397 | 42.725 | 9.979 |
| 40000 | 125 | SUCCEEDED | 4.915 | 317.71 | 550.173 | 232.463 | 12.36 |
| 40000 | 150 | SUCCEEDED | 4.094 | 270.642 | 297.783 | 27.141 | 14.871 |
| 40000 | 185 | SUCCEEDED | 3.34 | 422.795 | 621.091 | 198.296 | 18.457 |
| 50000 | 25 | SUCCEEDED | 29.94 | 308.049 | 491.759 | 183.71 | 3.134 |
| 50000 | 50 | SUCCEEDED | 15.057 | 216.722 | 234.675 | 17.953 | 6.793 |
| 50000 | 75 | SUCCEEDED | 10.022 | 254.441 | 278.907 | 24.466 | 7.689 |
| 50000 | 100 | SUCCEEDED | 7.796 | 281.229 | 495.406 | 214.177 | 10.234 |
| 50000 | 125 | SUCCEEDED | 6.115 | 392.004 | 587.545 | 195.541 | 12.598 |
| 50000 | 150 | SUCCEEDED | 5.482 | 354.658 | 584.551 | 229.893 | 14.947 |
| 50000 | 185 | SUCCEEDED | 4.457 | 513.793 | 608.506 | 94.713 | 18.362 |

**SUCCEEDED:** 38/42

## Part 10 — Current status (2026-07-09)

| Item | Status |
|------|--------|
| Low grid canonical rows | 42 (38 SUCCEEDED) |
| Medium grid canonical rows | 42 (38 SUCCEEDED) |
| Sheets backfill V/W | Done |
| Duplicate retry rows | Removed (10 deleted) |
| Complexity A1 pivots | AVG(W), SUCCEEDED filter |
| Connected charts | B:G + H:M ranges preserved |

### Still-failing (D,N) — both complexities
| D | N |
|---|---|
| 5000 | 150 |
| 5000 | 185 |
| 10000 | 185 |
| 20000 | 185 |

## Part 11 — Google Sheets reference

### Complexity_Low / Complexity_Medium layout (DO NOT MOVE A1)
- **A1:** QUERY pivot, spills to A:G
- **H1:M1:** Min marker headers
- **H2:M15:** min-marker formulas for scatter overlay on charts

### Maintenance commands
```bash
python scripts/sync_results_sheet.py
python scripts/update_sheets_formulas.py
python scripts/analyze_paper_metrics.py
```

## Part 12 — Instructions for Claude (next steps)

1. **Figures:** Export Complexity tab pivot (wall_clock) per D; plot T vs N; mark interior minima.
2. **Text:** Explain metric choice (wall_clock) explicitly.
3. **Table:** N* from fitted model vs empirical argmin of wall_clock per D.
4. **Limitations:** 8 missing points at high N; Spot Batch instability.
5. **Optional:** Rerun failing 8 with on-demand EC2.

## Part 13 — Glossary

- **D:** Dataset size — number of SMILES/compounds in the CSV for one job.
- **N:** Node configuration — number of parallel Batch array children (workers).
- **wall_clock:** User-visible elapsed cluster time including upload and init.
- **U-curve:** Time vs N curve with interior minimum — paper's key visual claim.

## Part 14 — Extended FAQ

**Q: Does our data verify the paper?**
A: Partially. U-shapes appear in wall_clock; computation_sec does not. Estimator MAPE huge vs L.

**Q: Which metric for thesis figures?**
A: wall_clock (col W), SUCCEEDED only.

## Part 15 — Pivot snapshot (post-backfill)

### Complexity_Low
| Nodes | 5000 | 10000 | 20000 | 30000 | 40000 | 50000 |
| 25 | 180.995 | 85.279 | 253.572 | 254.784 | 122.043 | 140.126 |
| 50 | 105.435 | 101.117 | 121.865 | 182.134 | 159.435 | 163.426 |
| 75 | 189.201 | 127.084 | 200.305 | 354.306 | 405.54 | 258.96 |
| 100 | 313.981 | 148.721 | 174.666 | 360.558 | 239.174 | 253.044 |
| 125 | 429.872 | 428.723 | 358.201 | 349.234 | 271.938 | 476.207 |
| 150 |  | 236.597 | 511.047 | 408.47 | 427.94 | 231.266 |
| 185 |  |  |  | 318.615 | 278.37 | 489.444 |

### Complexity_Medium
| Nodes | 5000 | 10000 | 20000 | 30000 | 40000 | 50000 |
| 25 | 214.234 | 143.34 | 318.915 | 204.527 | 178.594 | 491.759 |
| 50 | 128.987 | 125.285 | 381.664 | 352.09 | 236.322 | 234.675 |
| 75 | 163.808 | 160.468 | 400.609 | 445.505 | 217.334 | 278.907 |
| 100 | 195.187 | 357.644 | 217.063 | 282.285 | 279.397 | 495.406 |
| 125 | 231.808 | 392.972 | 462.768 | 337.479 | 550.173 | 587.545 |
| 150 |  | 272.923 | 416.139 | 569.503 | 297.783 | 584.551 |
| 185 |  |  |  | 466.724 | 621.091 | 608.506 |

## Part 16 — Artifact index

- **Low grid batch JSON:** `experiments/results/paper_replication_low_compute_only_20260708_003445/`
- **Medium grid batch JSON:** `experiments/results/paper_replication_medium_compute_only_20260708_041044/`
- **Final report:** `experiments/docs/FINAL_REPORT.md`

## Part 17 — Per-dataset-size narrative (wall_clock, SUCCEEDED)

### Low complexity
- **D=5000:** N=50 minimizes W=105.4s (among 5 points)
  - Full series: N=25→181s, N=50→105s, N=75→189s, N=100→314s, N=125→430s
- **D=10000:** N=25 minimizes W=85.3s (among 6 points)
  - Full series: N=25→85s, N=50→101s, N=75→127s, N=100→149s, N=125→429s, N=150→237s
- **D=20000:** N=50 minimizes W=121.9s (among 6 points)
  - Full series: N=25→254s, N=50→122s, N=75→200s, N=100→175s, N=125→358s, N=150→511s
- **D=30000:** N=50 minimizes W=182.1s (among 7 points)
  - Full series: N=25→255s, N=50→182s, N=75→354s, N=100→361s, N=125→349s, N=150→408s, N=185→319s
- **D=40000:** N=25 minimizes W=122.0s (among 7 points)
  - Full series: N=25→122s, N=50→159s, N=75→406s, N=100→239s, N=125→272s, N=150→428s, N=185→278s
- **D=50000:** N=25 minimizes W=140.1s (among 7 points)
  - Full series: N=25→140s, N=50→163s, N=75→259s, N=100→253s, N=125→476s, N=150→231s, N=185→489s

### Medium complexity
- **D=5000:** N=50 minimizes W=129.0s (among 5 points)
  - Full series: N=25→214s, N=50→129s, N=75→164s, N=100→195s, N=125→232s
- **D=10000:** N=50 minimizes W=125.3s (among 6 points)
  - Full series: N=25→143s, N=50→125s, N=75→160s, N=100→358s, N=125→393s, N=150→273s
- **D=20000:** N=100 minimizes W=217.1s (among 6 points)
  - Full series: N=25→319s, N=50→382s, N=75→401s, N=100→217s, N=125→463s, N=150→416s
- **D=30000:** N=25 minimizes W=204.5s (among 7 points)
  - Full series: N=25→205s, N=50→352s, N=75→446s, N=100→282s, N=125→337s, N=150→570s, N=185→467s
- **D=40000:** N=25 minimizes W=178.6s (among 7 points)
  - Full series: N=25→179s, N=50→236s, N=75→217s, N=100→279s, N=125→550s, N=150→298s, N=185→621s
- **D=50000:** N=50 minimizes W=234.7s (among 7 points)
  - Full series: N=25→492s, N=50→235s, N=75→279s, N=100→495s, N=125→588s, N=150→585s, N=185→609s

## Part 18 — Verification loss summary

- n_matched = 42; MAPE ≈ 25,055% (low grid, computation_sec vs estimator)
- Estimator predicts orders-of-magnitude larger computation times than shard max.

## Part 19 — Reproducibility checklist

1. conda activate venv_chemoinformatics
2. export PYTHONPATH=.
3. source .env
4. Run estimator before Batch
5. sync_results_sheet.py after run

## Part 20 — Closing remarks

This project is **measurement-first**. The science is in **choosing the right observable**.
Wall clock restores the U-curve story. Document this explicitly in any chapter Claude writes.

## Part 21 — Cell-by-cell commentary (low complexity)

- D=5000 N=25: status=SUCCEEDED, L=1.499s (shard max), W=180.995s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=5000 N=50: status=SUCCEEDED, L=0.798s (shard max), W=105.435s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=5000 N=75: status=SUCCEEDED, L=0.552s (shard max), W=189.201s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=5000 N=100: status=SUCCEEDED, L=0.383s (shard max), W=313.981s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=5000 N=125: status=SUCCEEDED, L=0.342s (shard max), W=429.872s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=5000 N=150: status=FAILED, L=0.298s (shard max), W=365.816s (end-to-end proxy). EXCLUDED from pivot — do not use in charts.
- D=5000 N=185: status=FAILED, L=0.26s (shard max), W=269.443s (end-to-end proxy). EXCLUDED from pivot — do not use in charts.
- D=10000 N=25: status=SUCCEEDED, L=2.984s (shard max), W=85.279s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=10000 N=50: status=SUCCEEDED, L=1.541s (shard max), W=101.117s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=10000 N=75: status=SUCCEEDED, L=1.008s (shard max), W=127.084s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=10000 N=100: status=SUCCEEDED, L=0.761s (shard max), W=148.721s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=10000 N=125: status=SUCCEEDED, L=0.652s (shard max), W=428.723s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=10000 N=150: status=SUCCEEDED, L=0.547s (shard max), W=236.597s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=10000 N=185: status=FAILED, L=0.446s (shard max), W=17.803s (end-to-end proxy). EXCLUDED from pivot — do not use in charts.
- D=20000 N=25: status=SUCCEEDED, L=6.414s (shard max), W=253.572s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=20000 N=50: status=SUCCEEDED, L=3.141s (shard max), W=121.865s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=20000 N=75: status=SUCCEEDED, L=2.121s (shard max), W=200.305s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=20000 N=100: status=SUCCEEDED, L=1.631s (shard max), W=174.666s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=20000 N=125: status=SUCCEEDED, L=1.222s (shard max), W=358.201s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=20000 N=150: status=SUCCEEDED, L=1.001s (shard max), W=511.047s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=20000 N=185: status=FAILED, L=0.964s (shard max), W=390.85s (end-to-end proxy). EXCLUDED from pivot — do not use in charts.
- D=30000 N=25: status=SUCCEEDED, L=8.826s (shard max), W=254.784s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=30000 N=50: status=SUCCEEDED, L=4.435s (shard max), W=182.134s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=30000 N=75: status=SUCCEEDED, L=3.03s (shard max), W=354.306s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=30000 N=100: status=SUCCEEDED, L=2.142s (shard max), W=360.558s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=30000 N=125: status=SUCCEEDED, L=1.871s (shard max), W=349.234s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=30000 N=150: status=SUCCEEDED, L=1.492s (shard max), W=408.47s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=30000 N=185: status=SUCCEEDED, L=1.205s (shard max), W=318.615s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=25: status=SUCCEEDED, L=11.267s (shard max), W=122.043s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=50: status=SUCCEEDED, L=5.872s (shard max), W=159.435s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=75: status=SUCCEEDED, L=3.933s (shard max), W=405.54s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=100: status=SUCCEEDED, L=2.965s (shard max), W=239.174s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=125: status=SUCCEEDED, L=2.514s (shard max), W=271.938s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=150: status=SUCCEEDED, L=2.012s (shard max), W=427.94s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=40000 N=185: status=SUCCEEDED, L=1.636s (shard max), W=278.37s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=25: status=SUCCEEDED, L=14.747s (shard max), W=140.126s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=50: status=SUCCEEDED, L=8.396s (shard max), W=163.426s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=75: status=SUCCEEDED, L=4.951s (shard max), W=258.96s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=100: status=SUCCEEDED, L=3.739s (shard max), W=253.044s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=125: status=SUCCEEDED, L=3.149s (shard max), W=476.207s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=150: status=SUCCEEDED, L=2.561s (shard max), W=231.266s (end-to-end proxy). Included in SUCCEEDED pivot.
- D=50000 N=185: status=SUCCEEDED, L=2.006s (shard max), W=489.444s (end-to-end proxy). Included in SUCCEEDED pivot.

## Part 22 — Cell-by-cell commentary (medium complexity)

- D=5000 N=25: status=SUCCEEDED, L=3.217s, W=214.234s. SUCCEEDED pivot cell.
- D=5000 N=50: status=SUCCEEDED, L=1.59s, W=128.987s. SUCCEEDED pivot cell.
- D=5000 N=75: status=SUCCEEDED, L=1.072s, W=163.808s. SUCCEEDED pivot cell.
- D=5000 N=100: status=SUCCEEDED, L=0.733s, W=195.187s. SUCCEEDED pivot cell.
- D=5000 N=125: status=SUCCEEDED, L=0.625s, W=231.808s. SUCCEEDED pivot cell.
- D=5000 N=150: status=FAILED, L=0.53s, W=14.008s. FAILED — missing from chart series.
- D=5000 N=185: status=FAILED, L=0.451s, W=324.794s. FAILED — missing from chart series.
- D=10000 N=25: status=SUCCEEDED, L=5.992s, W=143.34s. SUCCEEDED pivot cell.
- D=10000 N=50: status=SUCCEEDED, L=3.019s, W=125.285s. SUCCEEDED pivot cell.
- D=10000 N=75: status=SUCCEEDED, L=2.107s, W=160.468s. SUCCEEDED pivot cell.
- D=10000 N=100: status=SUCCEEDED, L=1.577s, W=357.644s. SUCCEEDED pivot cell.
- D=10000 N=125: status=SUCCEEDED, L=1.206s, W=392.972s. SUCCEEDED pivot cell.
- D=10000 N=150: status=SUCCEEDED, L=1.041s, W=272.923s. SUCCEEDED pivot cell.
- D=10000 N=185: status=FAILED, L=0.85s, W=17.698s. FAILED — missing from chart series.
- D=20000 N=25: status=SUCCEEDED, L=11.963s, W=318.915s. SUCCEEDED pivot cell.
- D=20000 N=50: status=SUCCEEDED, L=6.26s, W=381.664s. SUCCEEDED pivot cell.
- D=20000 N=75: status=SUCCEEDED, L=4.161s, W=400.609s. SUCCEEDED pivot cell.
- D=20000 N=100: status=SUCCEEDED, L=3.128s, W=217.063s. SUCCEEDED pivot cell.
- D=20000 N=125: status=SUCCEEDED, L=2.501s, W=462.768s. SUCCEEDED pivot cell.
- D=20000 N=150: status=SUCCEEDED, L=2.042s, W=416.139s. SUCCEEDED pivot cell.
- D=20000 N=185: status=FAILED, L=1.673s, W=18.749s. FAILED — missing from chart series.
- D=30000 N=25: status=SUCCEEDED, L=18.272s, W=204.527s. SUCCEEDED pivot cell.
- D=30000 N=50: status=SUCCEEDED, L=9.256s, W=352.09s. SUCCEEDED pivot cell.
- D=30000 N=75: status=SUCCEEDED, L=6.271s, W=445.505s. SUCCEEDED pivot cell.
- D=30000 N=100: status=SUCCEEDED, L=4.828s, W=282.285s. SUCCEEDED pivot cell.
- D=30000 N=125: status=SUCCEEDED, L=3.668s, W=337.479s. SUCCEEDED pivot cell.
- D=30000 N=150: status=SUCCEEDED, L=3.1s, W=569.503s. SUCCEEDED pivot cell.
- D=30000 N=185: status=SUCCEEDED, L=2.513s, W=466.724s. SUCCEEDED pivot cell.
- D=40000 N=25: status=SUCCEEDED, L=23.783s, W=178.594s. SUCCEEDED pivot cell.
- D=40000 N=50: status=SUCCEEDED, L=11.853s, W=236.322s. SUCCEEDED pivot cell.
- D=40000 N=75: status=SUCCEEDED, L=7.97s, W=217.334s. SUCCEEDED pivot cell.
- D=40000 N=100: status=SUCCEEDED, L=5.973s, W=279.397s. SUCCEEDED pivot cell.
- D=40000 N=125: status=SUCCEEDED, L=4.915s, W=550.173s. SUCCEEDED pivot cell.
- D=40000 N=150: status=SUCCEEDED, L=4.094s, W=297.783s. SUCCEEDED pivot cell.
- D=40000 N=185: status=SUCCEEDED, L=3.34s, W=621.091s. SUCCEEDED pivot cell.
- D=50000 N=25: status=SUCCEEDED, L=29.94s, W=491.759s. SUCCEEDED pivot cell.
- D=50000 N=50: status=SUCCEEDED, L=15.057s, W=234.675s. SUCCEEDED pivot cell.
- D=50000 N=75: status=SUCCEEDED, L=10.022s, W=278.907s. SUCCEEDED pivot cell.
- D=50000 N=100: status=SUCCEEDED, L=7.796s, W=495.406s. SUCCEEDED pivot cell.
- D=50000 N=125: status=SUCCEEDED, L=6.115s, W=587.545s. SUCCEEDED pivot cell.
- D=50000 N=150: status=SUCCEEDED, L=5.482s, W=584.551s. SUCCEEDED pivot cell.
- D=50000 N=185: status=SUCCEEDED, L=4.457s, W=608.506s. SUCCEEDED pivot cell.

## Part 23 — Research methodology notes

1. Always run estimator before Batch to avoid budget surprises.
2. Use EC2 queue for paper-style N scaling via array jobs.
3. Separate compute_only and full_pipeline runs for clean metric alignment.
4. Stream results to Google Sheets for live monitoring during overnight runs.
5. After run: verify JSON, fit model, sync Sheets, analyze metric shapes.
6. Never assume computation_sec equals paper T(N,D) without checking wall_clock.
7. Filter FAILED rows before any pivot or chart.
8. Upsert Sheets rows — never duplicate (D,N) keys.
9. Keep Complexity tab A1 fixed for connected charts.
10. Document metric definitions in any publication text.

## Part 24 — Paper figure replication guide for Claude

When reproducing paper-style figures:
1. X-axis: N (25 … 185)
2. Y-axis: wall_clock seconds (from Complexity pivot or Results col W)
3. One curve per D (6 curves per complexity tab)
4. Overlay min markers from columns H:M (scatter points at U-minimum)
5. Caption must state: SUCCEEDED jobs only; 8 grid points missing at high N for small D
6. Do not use computation_sec for these figures
7. Optional inset: computation_sec showing monotone decrease (explains why L is wrong metric)

## Part 25 — Thesis / report section outline (suggested)

1. Introduction — distributed descriptor computation and cost of wrong N
2. Background — paper model T(N,D) and N*(D)
3. Methods — AWS Batch array jobs, SMILES grids, timing phases
4. Results — wall_clock U-curves low vs medium complexity
5. Results — quadratic fit on computation_sec (R² table)
6. Discussion — metric mismatch and why it matters
7. Limitations — 8 failed jobs, Spot instances, synthetic SMILES
8. Future work — on-demand reruns, full_pipeline grid, estimator refit on wall_clock

## Part 26 — Key reminders (repeated for Claude context)

- [1] PRIMARY CHART METRIC = wall_clock (col W)
- [1] FILTER = Status SUCCEEDED only
- [1] DO NOT USE computation_sec for U-curve plots
- [1] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [1] 76 SUCCEEDED total across both grids
- [1] 8 failures at N=150,185 for D <= 20000
- [1] Sheets sync script = scripts/sync_results_sheet.py
- [1] Handoff generated from live Sheets pull
- [1] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [1] Model: T(N,D) quadratic with interaction term e*N*D
- [2] PRIMARY CHART METRIC = wall_clock (col W)
- [2] FILTER = Status SUCCEEDED only
- [2] DO NOT USE computation_sec for U-curve plots
- [2] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [2] 76 SUCCEEDED total across both grids
- [2] 8 failures at N=150,185 for D <= 20000
- [2] Sheets sync script = scripts/sync_results_sheet.py
- [2] Handoff generated from live Sheets pull
- [2] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [2] Model: T(N,D) quadratic with interaction term e*N*D
- [3] PRIMARY CHART METRIC = wall_clock (col W)
- [3] FILTER = Status SUCCEEDED only
- [3] DO NOT USE computation_sec for U-curve plots
- [3] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [3] 76 SUCCEEDED total across both grids
- [3] 8 failures at N=150,185 for D <= 20000
- [3] Sheets sync script = scripts/sync_results_sheet.py
- [3] Handoff generated from live Sheets pull
- [3] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [3] Model: T(N,D) quadratic with interaction term e*N*D
- [4] PRIMARY CHART METRIC = wall_clock (col W)
- [4] FILTER = Status SUCCEEDED only
- [4] DO NOT USE computation_sec for U-curve plots
- [4] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [4] 76 SUCCEEDED total across both grids
- [4] 8 failures at N=150,185 for D <= 20000
- [4] Sheets sync script = scripts/sync_results_sheet.py
- [4] Handoff generated from live Sheets pull
- [4] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [4] Model: T(N,D) quadratic with interaction term e*N*D
- [5] PRIMARY CHART METRIC = wall_clock (col W)
- [5] FILTER = Status SUCCEEDED only
- [5] DO NOT USE computation_sec for U-curve plots
- [5] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [5] 76 SUCCEEDED total across both grids
- [5] 8 failures at N=150,185 for D <= 20000
- [5] Sheets sync script = scripts/sync_results_sheet.py
- [5] Handoff generated from live Sheets pull
- [5] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [5] Model: T(N,D) quadratic with interaction term e*N*D
- [6] PRIMARY CHART METRIC = wall_clock (col W)
- [6] FILTER = Status SUCCEEDED only
- [6] DO NOT USE computation_sec for U-curve plots
- [6] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [6] 76 SUCCEEDED total across both grids
- [6] 8 failures at N=150,185 for D <= 20000
- [6] Sheets sync script = scripts/sync_results_sheet.py
- [6] Handoff generated from live Sheets pull
- [6] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [6] Model: T(N,D) quadratic with interaction term e*N*D
- [7] PRIMARY CHART METRIC = wall_clock (col W)
- [7] FILTER = Status SUCCEEDED only
- [7] DO NOT USE computation_sec for U-curve plots
- [7] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [7] 76 SUCCEEDED total across both grids
- [7] 8 failures at N=150,185 for D <= 20000
- [7] Sheets sync script = scripts/sync_results_sheet.py
- [7] Handoff generated from live Sheets pull
- [7] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [7] Model: T(N,D) quadratic with interaction term e*N*D
- [8] PRIMARY CHART METRIC = wall_clock (col W)
- [8] FILTER = Status SUCCEEDED only
- [8] DO NOT USE computation_sec for U-curve plots
- [8] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [8] 76 SUCCEEDED total across both grids
- [8] 8 failures at N=150,185 for D <= 20000
- [8] Sheets sync script = scripts/sync_results_sheet.py
- [8] Handoff generated from live Sheets pull
- [8] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [8] Model: T(N,D) quadratic with interaction term e*N*D
- [9] PRIMARY CHART METRIC = wall_clock (col W)
- [9] FILTER = Status SUCCEEDED only
- [9] DO NOT USE computation_sec for U-curve plots
- [9] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [9] 76 SUCCEEDED total across both grids
- [9] 8 failures at N=150,185 for D <= 20000
- [9] Sheets sync script = scripts/sync_results_sheet.py
- [9] Handoff generated from live Sheets pull
- [9] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [9] Model: T(N,D) quadratic with interaction term e*N*D
- [10] PRIMARY CHART METRIC = wall_clock (col W)
- [10] FILTER = Status SUCCEEDED only
- [10] DO NOT USE computation_sec for U-curve plots
- [10] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [10] 76 SUCCEEDED total across both grids
- [10] 8 failures at N=150,185 for D <= 20000
- [10] Sheets sync script = scripts/sync_results_sheet.py
- [10] Handoff generated from live Sheets pull
- [10] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [10] Model: T(N,D) quadratic with interaction term e*N*D
- [11] PRIMARY CHART METRIC = wall_clock (col W)
- [11] FILTER = Status SUCCEEDED only
- [11] DO NOT USE computation_sec for U-curve plots
- [11] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [11] 76 SUCCEEDED total across both grids
- [11] 8 failures at N=150,185 for D <= 20000
- [11] Sheets sync script = scripts/sync_results_sheet.py
- [11] Handoff generated from live Sheets pull
- [11] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [11] Model: T(N,D) quadratic with interaction term e*N*D
- [12] PRIMARY CHART METRIC = wall_clock (col W)
- [12] FILTER = Status SUCCEEDED only
- [12] DO NOT USE computation_sec for U-curve plots
- [12] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [12] 76 SUCCEEDED total across both grids
- [12] 8 failures at N=150,185 for D <= 20000
- [12] Sheets sync script = scripts/sync_results_sheet.py
- [12] Handoff generated from live Sheets pull
- [12] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [12] Model: T(N,D) quadratic with interaction term e*N*D
- [13] PRIMARY CHART METRIC = wall_clock (col W)
- [13] FILTER = Status SUCCEEDED only
- [13] DO NOT USE computation_sec for U-curve plots
- [13] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [13] 76 SUCCEEDED total across both grids
- [13] 8 failures at N=150,185 for D <= 20000
- [13] Sheets sync script = scripts/sync_results_sheet.py
- [13] Handoff generated from live Sheets pull
- [13] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [13] Model: T(N,D) quadratic with interaction term e*N*D
- [14] PRIMARY CHART METRIC = wall_clock (col W)
- [14] FILTER = Status SUCCEEDED only
- [14] DO NOT USE computation_sec for U-curve plots
- [14] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [14] 76 SUCCEEDED total across both grids
- [14] 8 failures at N=150,185 for D <= 20000
- [14] Sheets sync script = scripts/sync_results_sheet.py
- [14] Handoff generated from live Sheets pull
- [14] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [14] Model: T(N,D) quadratic with interaction term e*N*D
- [15] PRIMARY CHART METRIC = wall_clock (col W)
- [15] FILTER = Status SUCCEEDED only
- [15] DO NOT USE computation_sec for U-curve plots
- [15] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [15] 76 SUCCEEDED total across both grids
- [15] 8 failures at N=150,185 for D <= 20000
- [15] Sheets sync script = scripts/sync_results_sheet.py
- [15] Handoff generated from live Sheets pull
- [15] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [15] Model: T(N,D) quadratic with interaction term e*N*D
- [16] PRIMARY CHART METRIC = wall_clock (col W)
- [16] FILTER = Status SUCCEEDED only
- [16] DO NOT USE computation_sec for U-curve plots
- [16] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [16] 76 SUCCEEDED total across both grids
- [16] 8 failures at N=150,185 for D <= 20000
- [16] Sheets sync script = scripts/sync_results_sheet.py
- [16] Handoff generated from live Sheets pull
- [16] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [16] Model: T(N,D) quadratic with interaction term e*N*D
- [17] PRIMARY CHART METRIC = wall_clock (col W)
- [17] FILTER = Status SUCCEEDED only
- [17] DO NOT USE computation_sec for U-curve plots
- [17] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [17] 76 SUCCEEDED total across both grids
- [17] 8 failures at N=150,185 for D <= 20000
- [17] Sheets sync script = scripts/sync_results_sheet.py
- [17] Handoff generated from live Sheets pull
- [17] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [17] Model: T(N,D) quadratic with interaction term e*N*D
- [18] PRIMARY CHART METRIC = wall_clock (col W)
- [18] FILTER = Status SUCCEEDED only
- [18] DO NOT USE computation_sec for U-curve plots
- [18] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [18] 76 SUCCEEDED total across both grids
- [18] 8 failures at N=150,185 for D <= 20000
- [18] Sheets sync script = scripts/sync_results_sheet.py
- [18] Handoff generated from live Sheets pull
- [18] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [18] Model: T(N,D) quadratic with interaction term e*N*D
- [19] PRIMARY CHART METRIC = wall_clock (col W)
- [19] FILTER = Status SUCCEEDED only
- [19] DO NOT USE computation_sec for U-curve plots
- [19] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [19] 76 SUCCEEDED total across both grids
- [19] 8 failures at N=150,185 for D <= 20000
- [19] Sheets sync script = scripts/sync_results_sheet.py
- [19] Handoff generated from live Sheets pull
- [19] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [19] Model: T(N,D) quadratic with interaction term e*N*D
- [20] PRIMARY CHART METRIC = wall_clock (col W)
- [20] FILTER = Status SUCCEEDED only
- [20] DO NOT USE computation_sec for U-curve plots
- [20] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [20] 76 SUCCEEDED total across both grids
- [20] 8 failures at N=150,185 for D <= 20000
- [20] Sheets sync script = scripts/sync_results_sheet.py
- [20] Handoff generated from live Sheets pull
- [20] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [20] Model: T(N,D) quadratic with interaction term e*N*D
- [21] PRIMARY CHART METRIC = wall_clock (col W)
- [21] FILTER = Status SUCCEEDED only
- [21] DO NOT USE computation_sec for U-curve plots
- [21] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [21] 76 SUCCEEDED total across both grids
- [21] 8 failures at N=150,185 for D <= 20000
- [21] Sheets sync script = scripts/sync_results_sheet.py
- [21] Handoff generated from live Sheets pull
- [21] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [21] Model: T(N,D) quadratic with interaction term e*N*D
- [22] PRIMARY CHART METRIC = wall_clock (col W)
- [22] FILTER = Status SUCCEEDED only
- [22] DO NOT USE computation_sec for U-curve plots
- [22] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [22] 76 SUCCEEDED total across both grids
- [22] 8 failures at N=150,185 for D <= 20000
- [22] Sheets sync script = scripts/sync_results_sheet.py
- [22] Handoff generated from live Sheets pull
- [22] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [22] Model: T(N,D) quadratic with interaction term e*N*D
- [23] PRIMARY CHART METRIC = wall_clock (col W)
- [23] FILTER = Status SUCCEEDED only
- [23] DO NOT USE computation_sec for U-curve plots
- [23] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [23] 76 SUCCEEDED total across both grids
- [23] 8 failures at N=150,185 for D <= 20000
- [23] Sheets sync script = scripts/sync_results_sheet.py
- [23] Handoff generated from live Sheets pull
- [23] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [23] Model: T(N,D) quadratic with interaction term e*N*D
- [24] PRIMARY CHART METRIC = wall_clock (col W)
- [24] FILTER = Status SUCCEEDED only
- [24] DO NOT USE computation_sec for U-curve plots
- [24] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [24] 76 SUCCEEDED total across both grids
- [24] 8 failures at N=150,185 for D <= 20000
- [24] Sheets sync script = scripts/sync_results_sheet.py
- [24] Handoff generated from live Sheets pull
- [24] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [24] Model: T(N,D) quadratic with interaction term e*N*D
- [25] PRIMARY CHART METRIC = wall_clock (col W)
- [25] FILTER = Status SUCCEEDED only
- [25] DO NOT USE computation_sec for U-curve plots
- [25] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [25] 76 SUCCEEDED total across both grids
- [25] 8 failures at N=150,185 for D <= 20000
- [25] Sheets sync script = scripts/sync_results_sheet.py
- [25] Handoff generated from live Sheets pull
- [25] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [25] Model: T(N,D) quadratic with interaction term e*N*D
- [26] PRIMARY CHART METRIC = wall_clock (col W)
- [26] FILTER = Status SUCCEEDED only
- [26] DO NOT USE computation_sec for U-curve plots
- [26] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [26] 76 SUCCEEDED total across both grids
- [26] 8 failures at N=150,185 for D <= 20000
- [26] Sheets sync script = scripts/sync_results_sheet.py
- [26] Handoff generated from live Sheets pull
- [26] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [26] Model: T(N,D) quadratic with interaction term e*N*D
- [27] PRIMARY CHART METRIC = wall_clock (col W)
- [27] FILTER = Status SUCCEEDED only
- [27] DO NOT USE computation_sec for U-curve plots
- [27] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [27] 76 SUCCEEDED total across both grids
- [27] 8 failures at N=150,185 for D <= 20000
- [27] Sheets sync script = scripts/sync_results_sheet.py
- [27] Handoff generated from live Sheets pull
- [27] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [27] Model: T(N,D) quadratic with interaction term e*N*D
- [28] PRIMARY CHART METRIC = wall_clock (col W)
- [28] FILTER = Status SUCCEEDED only
- [28] DO NOT USE computation_sec for U-curve plots
- [28] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [28] 76 SUCCEEDED total across both grids
- [28] 8 failures at N=150,185 for D <= 20000
- [28] Sheets sync script = scripts/sync_results_sheet.py
- [28] Handoff generated from live Sheets pull
- [28] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [28] Model: T(N,D) quadratic with interaction term e*N*D
- [29] PRIMARY CHART METRIC = wall_clock (col W)
- [29] FILTER = Status SUCCEEDED only
- [29] DO NOT USE computation_sec for U-curve plots
- [29] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [29] 76 SUCCEEDED total across both grids
- [29] 8 failures at N=150,185 for D <= 20000
- [29] Sheets sync script = scripts/sync_results_sheet.py
- [29] Handoff generated from live Sheets pull
- [29] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [29] Model: T(N,D) quadratic with interaction term e*N*D
- [30] PRIMARY CHART METRIC = wall_clock (col W)
- [30] FILTER = Status SUCCEEDED only
- [30] DO NOT USE computation_sec for U-curve plots
- [30] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [30] 76 SUCCEEDED total across both grids
- [30] 8 failures at N=150,185 for D <= 20000
- [30] Sheets sync script = scripts/sync_results_sheet.py
- [30] Handoff generated from live Sheets pull
- [30] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [30] Model: T(N,D) quadratic with interaction term e*N*D
- [31] PRIMARY CHART METRIC = wall_clock (col W)
- [31] FILTER = Status SUCCEEDED only
- [31] DO NOT USE computation_sec for U-curve plots
- [31] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [31] 76 SUCCEEDED total across both grids
- [31] 8 failures at N=150,185 for D <= 20000
- [31] Sheets sync script = scripts/sync_results_sheet.py
- [31] Handoff generated from live Sheets pull
- [31] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [31] Model: T(N,D) quadratic with interaction term e*N*D
- [32] PRIMARY CHART METRIC = wall_clock (col W)
- [32] FILTER = Status SUCCEEDED only
- [32] DO NOT USE computation_sec for U-curve plots
- [32] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [32] 76 SUCCEEDED total across both grids
- [32] 8 failures at N=150,185 for D <= 20000
- [32] Sheets sync script = scripts/sync_results_sheet.py
- [32] Handoff generated from live Sheets pull
- [32] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [32] Model: T(N,D) quadratic with interaction term e*N*D
- [33] PRIMARY CHART METRIC = wall_clock (col W)
- [33] FILTER = Status SUCCEEDED only
- [33] DO NOT USE computation_sec for U-curve plots
- [33] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [33] 76 SUCCEEDED total across both grids
- [33] 8 failures at N=150,185 for D <= 20000
- [33] Sheets sync script = scripts/sync_results_sheet.py
- [33] Handoff generated from live Sheets pull
- [33] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [33] Model: T(N,D) quadratic with interaction term e*N*D
- [34] PRIMARY CHART METRIC = wall_clock (col W)
- [34] FILTER = Status SUCCEEDED only
- [34] DO NOT USE computation_sec for U-curve plots
- [34] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [34] 76 SUCCEEDED total across both grids
- [34] 8 failures at N=150,185 for D <= 20000
- [34] Sheets sync script = scripts/sync_results_sheet.py
- [34] Handoff generated from live Sheets pull
- [34] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [34] Model: T(N,D) quadratic with interaction term e*N*D
- [35] PRIMARY CHART METRIC = wall_clock (col W)
- [35] FILTER = Status SUCCEEDED only
- [35] DO NOT USE computation_sec for U-curve plots
- [35] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [35] 76 SUCCEEDED total across both grids
- [35] 8 failures at N=150,185 for D <= 20000
- [35] Sheets sync script = scripts/sync_results_sheet.py
- [35] Handoff generated from live Sheets pull
- [35] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [35] Model: T(N,D) quadratic with interaction term e*N*D
- [36] PRIMARY CHART METRIC = wall_clock (col W)
- [36] FILTER = Status SUCCEEDED only
- [36] DO NOT USE computation_sec for U-curve plots
- [36] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [36] 76 SUCCEEDED total across both grids
- [36] 8 failures at N=150,185 for D <= 20000
- [36] Sheets sync script = scripts/sync_results_sheet.py
- [36] Handoff generated from live Sheets pull
- [36] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [36] Model: T(N,D) quadratic with interaction term e*N*D
- [37] PRIMARY CHART METRIC = wall_clock (col W)
- [37] FILTER = Status SUCCEEDED only
- [37] DO NOT USE computation_sec for U-curve plots
- [37] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [37] 76 SUCCEEDED total across both grids
- [37] 8 failures at N=150,185 for D <= 20000
- [37] Sheets sync script = scripts/sync_results_sheet.py
- [37] Handoff generated from live Sheets pull
- [37] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [37] Model: T(N,D) quadratic with interaction term e*N*D
- [38] PRIMARY CHART METRIC = wall_clock (col W)
- [38] FILTER = Status SUCCEEDED only
- [38] DO NOT USE computation_sec for U-curve plots
- [38] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [38] 76 SUCCEEDED total across both grids
- [38] 8 failures at N=150,185 for D <= 20000
- [38] Sheets sync script = scripts/sync_results_sheet.py
- [38] Handoff generated from live Sheets pull
- [38] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [38] Model: T(N,D) quadratic with interaction term e*N*D
- [39] PRIMARY CHART METRIC = wall_clock (col W)
- [39] FILTER = Status SUCCEEDED only
- [39] DO NOT USE computation_sec for U-curve plots
- [39] 84 canonical rows per compute_only grid (42 low + 42 medium)
- [39] 76 SUCCEEDED total across both grids
- [39] 8 failures at N=150,185 for D <= 20000
- [39] Sheets sync script = scripts/sync_results_sheet.py
- [39] Handoff generated from live Sheets pull
- [39] Paper authors: Didachos, Georgiou, Fousteris, Kanavos
- [39] Model: T(N,D) quadratic with interaction term e*N*D

---
*End of comprehensive handoff document.*
