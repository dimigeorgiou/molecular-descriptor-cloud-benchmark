# WHY LOW R² / LOOCV ON WALL-CLOCK (Paper2 established grid)

## TL;DR
- On the scoped `full_pipeline` low+medium grid (eligible cells: >=3 successful reps), wall-clock has weak predictive structure relative to replicate noise. This limits attainable R²/LOCOCV for smooth mean-surface models.
- Metric swap shows stronger structure on computation-centric metrics than on wall-clock: Christos quadratic performs materially better on `RealComputation` than `RealWallClock`.
- Christos quadratic is therefore **partially supported** on this sheet slice: stronger for compute-time behavior, weaker for end-to-end wall-clock prediction.

## 1) Data inventory
- Total rows in CSV: 1566
- Scoped rows (`ModeNorm=full_pipeline`, low+medium, target D/N): 265
- Scoped successful rows: 265
- Eligible rows (successful rows in cells with >=3 reps): 265 across 84 cells
- Replicate count per scoped successful cell: min/median/max = 3/3.0/4
- Spot/OD mix in eligible rows: {'unknown': 234, 'SPOT': 31}
- schema flags (scoped): {'shifted_v1': 234, 'modern': 31}
- is_shifted flags (scoped): {'True': 234, 'False': 31}
- Missing `RealWallClock` in scoped rows: 0
- Robust wall-clock outliers in scoped successful rows (MAD rule): 6

## 2) Variance anatomy of wall-clock (by pricing tier)
- Tier `SPOT`: n=31 rows, cells=31, between-cell η²=1.000, within/total=0.000, ICC≈1.000
- Tier `unknown`: n=234 rows, cells=84, between-cell η²=0.507, within/total=0.493, ICC≈0.236

Interpretation: low η²_between (or high within/total) means replicate noise dominates cell means, directly capping surface-model R².

## 3) Metric swap (same models, same eligible rows)
- `RealWallClock`: Christos R²=0.089, LOCO-R²=0.044; Amdahl-like R²=0.090, LOCO-R²=0.066
- `RealComputation`: Christos R²=0.391, LOCO-R²=0.357; Amdahl-like R²=0.347, LOCO-R²=0.331
- `RealClusterParallel`: Christos R²=0.191, LOCO-R²=0.151; Amdahl-like R²=0.187, LOCO-R²=0.164
- `RealTotalPipeline`: Christos R²=0.223, LOCO-R²=0.188; Amdahl-like R²=0.221, LOCO-R²=0.202

## 4) Christos quadratic vs Amdahl-like (focus: wall vs computation)
- Wall (`RealWallClock`), Christos: d=-7.87876e-06 (negative), LOCO-R²=0.044
- Wall, Amdahl-like LOCO-R²=0.066
- Computation (`RealComputation`), Christos: d=-0.000630683 (negative), LOCO-R²=0.357
- Computation, Amdahl-like LOCO-R²=0.331
- Christos interior N* in [25,185]:
  - Wall any interior N*? False
  - Computation any interior N*? False

## 5) Monotonicity / U-shape of median wall vs N
- low: D-series=6, interior-min count=3, boundary min at N=25 count=3
- medium: D-series=6, interior-min count=4, boundary min at N=25 count=2
- Shape counts by complexity: {'low': {'boundary_min_n25': 3, 'u_shape_interior_min': 3}, 'medium': {'boundary_min_n25': 2, 'u_shape_interior_min': 4}}

## 6) Effect sizes (magnitude-first)
- Spearman rho(wall, N) = 0.364
- Spearman rho(wall, D) = -0.010
- Spearman rho(wall, D/N) = -0.204
- Partial Pearson corr(wall, N | D) = 0.297
- Partial Pearson corr(wall, D | N) = -0.028
- Partial Pearson corr(wall, D/N | D,N) = -0.045
- Partial Spearman-like corr(wall, N | D) = 0.364
- Partial Spearman-like corr(wall, D | N) = -0.013

## 7) Why prior high R² reports can differ
- I searched repository `**/fitted_model.json` and collected entries with 0.6 <= R² <= 0.95.
- These fits often come from different run directories/modes and may be computation-centric, not the same wall-clock/full-pipeline slice used here.
- Evidence table is stored in `metrics.json` under `historical_r2_fits_0p6_to_0p95`, with exact paths and inferred mode/metric hints.

## 8) Christos proposal verdict for THIS sheet slice
**Verdict:** `partially_supported`

Evidence:
- On wall-clock (target of the concern), Christos LOCO-R² is 0.044, indicating weak out-of-cell generalization on this slice.
- On computation, Christos LOCO-R² is 0.357, stronger than wall-clock and consistent with better structural fit in compute metric.
- U-shape evidence in empirical medians is mixed (interior minima in 7/12 complexity×D series), not universal.

## Top 3 root causes (ranked by evidence strength)
1. **High within-cell replicate variability** (median within/total variance across tiers = 0.246).
2. **Noisy/non-universal wall-clock shape vs N** (interior-min fraction = 0.583 across complexity×D series).
3. **Metric mismatch** (LOCO-R² computation minus wall = 0.313 for Christos).

## Output artifacts
- `tmp/paper2_rebuild/investigation/metrics.json`
- `tmp/paper2_rebuild/investigation/WHY_LOW_R2_REPORT.md`
