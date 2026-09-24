# Investigation synthesis — why wall-clock R² is low + Christos check

Generated after isolated researcher + independent reviewer (no manuscript edits).

## Agents
- Researcher: unbiased forensic on `corrected_sheet_succeeded.csv` → `WHY_LOW_R2_REPORT.md`, `metrics.json`
- Reviewer: arithmetic PASS, interpretation corrections → `REVIEWER_NOTES.md`

## Corrected root-cause ranking (use this)

| Rank | Cause | Evidence |
|------|--------|----------|
| 1 | **Metric / claim mismatch** | Christos LOCO-R² wall 0.044 vs computation 0.357 (Δ≈+0.31, bootstrap-stable) |
| 2 | **Mean-surface misspecification on wall** | Oracle knowing cell means reaches R²≈0.45; smooth models only ≈0.09 → most gap is not noise alone |
| 3 | **High within-cell wall noise** | Pooled within/total ≈0.55 (ICC≈0.19). Do **not** quote the report’s “median 0.246” — that average was polluted by a 1-rep/cell SPOT subset |

Medians-vs-raw was a real Task-3 bug earlier, but it is **not** why R² stays low after raw-row refit.

## Christos (Didachos) proposal — re-checked

Paper model: \(T(N,D)=a+bN+cD+dN^2+eND\), interior \(N^*=-(b+eD)/(2d)\) **requires \(d>0\)** (convex U).

On **this** full_pipeline established-grid slice:
- Wall: weak fit; \(d\) **sign-unstable** under bootstrap (≈47% negative) — do not treat point-estimate \(d<0\) as settled.
- Computation: much better R², but still **no valid interior N\*** in [25,185] on this refit (and historical fits that reported R²≈0.9 used **aggregated 42-point** surfaces / often compute-centric metrics — different experiment).
- Empirical median wall vs N: **mixed** (7/12 series have an interior min; 5/12 min at N=25). Not a clean universal U.

**Verdict:** proposal is a useful *hypothesis for compute-phase scaling*, **not validated as an end-to-end wall-clock allocator** on the current full_pipeline Spot grid. Approach for the paper: separate (A) shard/compute scaling from (B) wall-clock / scheduling-dominated allocation; do not publish parametric \(N^*(D)\) from wall R²≈0.09.

## Practical approach (aligned with data)

1. Keep Task 4 cost model; OD/Spot headline **3.20×** from paired Task-1 audit.
2. For time: lead with **empirical** cell medians / config selector, not fitted \(N^*\).
3. If quoting Christos quadratic, restrict to **computation** (or compute_only historical) and disclose LOCO + aggregation caveats.
4. Limitations: wall full_pipeline surface is noisy + poorly captured by low-order polynomials; scheduling/init dominate wall variability.

## Artifacts
- `tmp/paper2_rebuild/investigation/WHY_LOW_R2_REPORT.md`
- `tmp/paper2_rebuild/investigation/metrics.json`
- `tmp/paper2_rebuild/investigation/REVIEWER_NOTES.md`
- `tmp/paper2_rebuild/investigation/run_forensic_analysis.py`
