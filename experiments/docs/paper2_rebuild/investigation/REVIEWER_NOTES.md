# REVIEWER NOTES — skeptical methods review of `WHY_LOW_R2_REPORT.md`

Reviewer: independent methods reviewer. Scope: internal consistency of the report vs `metrics.json`,
plus independent re-derivation of key claims from `tmp/paper2_rebuild/corrected_sheet_succeeded.csv`.

**Method.** All checks re-derived with a pure-stdlib script
(`tmp/paper2_rebuild/investigation/reviewer_check.py`, OLS by normal equations + Gaussian elimination)
that shares **no** numeric libraries with `run_forensic_analysis.py`. Agreement is therefore genuine
corroboration, not a re-run of the same code path. Uncertainty added in `reviewer_check2.py`
(600 cell-level bootstrap resamples). The repo's conda env has a broken NumPy ABI, so
`run_forensic_analysis.py` was not re-executed; it was read line by line instead.

**Overall trust level: MEDIUM — arithmetic fully reproducible, interpretation needs revision before use.**
Every number in the report traces correctly to `metrics.json` and to the CSV. The failures are
inferential, not arithmetic: the top-ranked root cause is mis-ranked, one headline statistic is a
degenerate artifact, the verdict label is a hardcoded default rather than a test result, and §7 omits
its own strongest available evidence.

---

## Reproduction of reported numbers — all matched

| Report claim | Reported | Independently re-derived |
|---|---|---|
| Total CSV rows | 1566 | 1566 |
| Mode split | compute_only 1136 / full_pipeline 430 | identical |
| Scoped / success / eligible rows | 265 / 265 / 265 in 84 cells | identical |
| Reps per cell min/med/max | 3 / 3.0 / 4 | identical |
| Tier mix | unknown 234, SPOT 31 | identical |
| Tier `unknown` η² / within-total / ICC | 0.507 / 0.493 / 0.236 | 0.50711 / 0.49289 / 0.23576 |
| Tier `SPOT` η² / within-total / ICC | 1.000 / 0.000 / 1.000 | 1.0 / 0.0 / 1.0 |
| Wall Christos R² / LOCO-R² | 0.089 / 0.044 | 0.089368 / 0.043542 |
| Computation Christos R² / LOCO-R² | 0.391 / 0.357 | 0.391401 / 0.356989 |
| Wall Christos `d` (N² coef) | −7.87876e−06 | −7.878760e−06 |
| Computation Christos `d` | −0.000630683 | −0.000630683 |
| Spearman ρ(wall, N) / ρ(wall, D) | 0.364 / −0.010 | 0.364036 / −0.010439 |
| MAD wall-clock outliers | 6 | 6 |

No transcription errors between `metrics.json` and the prose. Report §1–§6 are internally consistent.

---

## Check 1 — Are variance / ICC numbers correctly defined and plausible? **PARTIAL FAIL**

**Definitions: PASS.** η² = SS_between/SS_total and the one-way ICC
(MS_b − MS_w) / (MS_b + (k̄−1)·MS_w) with k̄ = mean reps/cell are both standard and correctly
implemented for an unbalanced design. Reproduced to 13 significant digits. Magnitudes (ICC ≈ 0.19–0.24)
are plausible for cloud wall-clock timing.

**Reporting: FAIL, two defects.**

1. **The `SPOT` row is structurally degenerate and is presented without caveat.** The decomposition is
   stratified by pricing tier *after* cells are defined, which splits each cell's replicates by tier.
   I confirmed all 31 SPOT rows fall in 31 **distinct** cells — exactly 1 rep per cell, and **0 of those
   31 cells are SPOT-only**. With one observation per cell, SS_within = 0 *by construction* (the
   reported 5.8e−11 is floating-point zero). η² = 1.000 and ICC = 1.000 carry zero information, yet
   §2 lists them beside the genuine `unknown` figures and the following sentence
   ("low η²_between … means replicate noise dominates") invites the reading that SPOT has no replicate
   noise. **Correction: drop the SPOT row or label it `degenerate — 1 rep/cell, ICC undefined`.**

2. **Root cause #1's headline number is an artifact.** "median within/total variance across tiers =
   0.246" is `median([0.000, 0.493])` — a two-element median that averages a real estimate with the
   degenerate zero, i.e. it is just their mean. The defensible figures are **0.554 pooled across all
   265 rows** (pooled η² = 0.446, pooled ICC = 0.193) or **0.493** for the only tier with replicates.
   The report therefore **understates its own top root cause by ~2.3×**. Correction: replace 0.246
   with 0.554 (pooled) and state which estimator is used.

**Additional finding — part of the "replicate noise" is a confound, not noise.** Cross-tabulation shows
pricing tier, schema and shift flag are **perfectly collinear**: `unknown|shifted_v1|is_shifted=True`
= 234 rows and `SPOT|modern|is_shifted=False` = 31 rows, zero off-diagonal. The 31 SPOT rows are also
the *only* `modern`/unshifted rows, and they sit inside cells otherwise populated by `shifted_v1` rows.
So pooled within-cell variance (0.554) exceeds single-tier variance (0.493) partly because a systematic
**schema-generation offset is being counted as replicate noise**. §1 lists the 234/31 counts three
times (tier, schema, is_shifted) without noting they are the same 31 rows, and the design is incapable
of separating tier from schema effects. This belongs in the caveats.

## Check 2 — Is the Christos `d < 0` claim correct for wall and computation? **PASS on arithmetic / FAIL on inferential weight**

Both signs are correct and reproduce exactly: wall `d` = −7.8788e−06, computation `d` = −6.3068e−04,
and `d_sign: "negative"` in `metrics.json` matches the prose. The `N* = null` convention when `d ≤ 0`
is defensible (no minimum exists) but is easy to misread as "not computable" — worth relabelling
`no_minimum_d_nonpositive`.

**However, the wall-clock sign is not a finding.** Cell-level bootstrap (600 resamples):

| Quantity | Point est. | Bootstrap median | 95% CI | Share of draws < 0 |
|---|---|---|---|---|
| Wall `d` (N²) | −7.88e−06 | **+2.85e−04** | [−8.17e−03, +7.01e−03] | **47.3 %** |
| Computation `d` (N²) | −6.31e−04 | −6.04e−04 | [−1.38e−03, +1.32e−04] | 93.5 % |

Wall `d` is a coin flip — the bootstrap median even has the *opposite* sign to the point estimate. §4
presents "d = −7.87876e−06 (negative)" to six significant figures as if it were a structural fact;
it is indistinguishable from zero. Computation `d < 0` is reasonably (not decisively) supported.

**Missing interpretation, and it cuts against the verdict.** `d < 0` makes the quadratic *concave* in N:
the stationary point is a **maximum**, so predicted time decreases without bound as N grows — physically
implausible (unbounded speedup) and the **opposite** of the U-shape the Christos proposal posits. This
holds on *both* metrics. §4 only says "any interior N*? False" and never states that the fitted shape is
anti-Christos on both metrics.

## Check 3 — Is the historical high-R² attribution evidenced with file paths? **PARTIAL FAIL**

**What holds up.** `metrics.json → historical_r2_fits_0p6_to_0p95` gives two real, verifiable paths;
I opened both and confirmed `r_squared` = 0.9175 and 0.9165. `mode: compute_only` is genuinely
evidenced (parsed from each run's `config.yaml`). §7's hedging ("may be", "inferred … hints") is
appropriate.

**What fails.**

1. **`metric_hint` is not evidence.** It is assigned by string-matching the *directory name* for
   "compute_only". Neither `fitted_model.json` contains any metric field — both hold only
   `{a,b,c,d,e,r_squared,fitted_from_n_samples,source}`. The report should say the metric is
   **unverified**, not "inferred hint".

2. **The decisive mechanism is present in the report's own data and goes unmentioned.** Both historical
   fits record `fitted_from_n_samples: 42` = 6 D × 7 N, i.e. they were fit to **aggregated per-cell
   points, per complexity separately** — not to 265 replicate rows. That removes within-cell noise and
   mechanically inflates R². I reproduced the effect: refitting the same Christos form to 42 per-cell
   median points gives **RealComputation R² = 0.768 (low) and 0.977 (medium)** versus 0.391 pooled at
   row level (wall: 0.268 / 0.108). So aggregation + per-complexity stratification explains the
   historical ≈0.92 far better than §7's "different modes / may be computation-centric". As written,
   §7 attributes the gap to the wrong cause.

3. **The key parameter flipped sign and this is not reported.** Historical `d` = **+0.000395** (low) and
   **+0.000816** (medium) — positive curvature, a genuine interior optimum. Current fits give `d < 0`.
   A sign flip in the parameter carrying the whole U-shape claim is a first-order finding.

4. **The R² filter hides the most extreme cases.** The `0.6 ≤ R² ≤ 0.95` window excludes fits above
   0.95. Only 4 `fitted_model.json` exist in the repo; the filter silently drops **2 of them** —
   `experiments/results/fitted_model.json` with **R² = 1.0** and
   `experiments/results/paper_alignment_mini_20260707_233519/fitted_model.json` with **R² = 0.9999**.
   These are exactly the "prior high R² reports" §7 was chartered to explain, and R² = 1.0 is itself a
   red flag (saturated/degenerate fit). Correction: report all 4 fits with no upper cutoff.

## Check 4 — Any overclaim or missing caveat? **FAIL — several**

1. **Root cause #1 is mis-ranked (most important correction).** An oracle that knows each cell's true
   mean achieves **R² = 0.446** on wall-clock (bootstrap CI 0.365–0.526). That is the noise ceiling.
   Christos reaches 0.089 — only ~20 % of the attainable signal. So ≈0.36 of the missing R² is
   **mean-surface misspecification**, not replicate noise. Replicate noise is real but is the *smaller*
   term; ranking it #1 while omitting the ceiling reverses the diagnosis. The TL;DR's "weak predictive
   structure **relative to replicate noise** … limits attainable R²" carries the same error.

2. **The verdict `partially_supported` is a hardcoded default, not a test result.** In
   `run_forensic_analysis.py`, `verdict` is initialised to `"partially_supported"` and can only change
   via two branches, both requiring `comp_any_interior` or a wall LOCO-R² ≥ 0.25. Since
   `comp_any_interior = False` and wall LOCO-R² = 0.044, **neither branch fires** and the default
   survives untouched. No evidence test produced this label, yet §8 presents it as a conclusion.
   Given `d < 0` and no interior N* on either metric, the supportable statement is: *the interior-optimum
   / U-shape claim is unsupported on both metrics; predictive accuracy is strongly metric-dependent.*

3. **Both stated data screens are no-ops, which is not disclosed.** All 1566 CSV rows are `SUCCEEDED`,
   and 0 cells have <3 reps. So "success_only_for_modeling" and "eligible_cells_min_reps: 3" excluded
   **nothing**. The framing "Scoped rows: 265 / Scoped successful rows: 265 / Eligible rows: 265"
   implies screening occurred. More importantly, any failed or censored runs were dropped **upstream** of
   this CSV, so **survivorship/selection bias is entirely unexamined** — a material gap in a "why is R²
   low" investigation, since truncating long-running or failed configurations flattens the response
   surface.

4. **No uncertainty anywhere.** Not one R², LOCO-R² or coefficient carries an interval. This matters for
   the model comparison: on wall-clock, Amdahl − Christos R² = −0.006, CI [−0.028, +0.005] — the two
   models are **indistinguishable**, so §4's juxtaposition of LOCO-R² 0.066 vs 0.044 must not be read as
   ranking them. Conversely, the metric-mismatch result is **robust**: computation − wall Christos R²
   = +0.296, CI [0.173, 0.431], 0/600 draws negative. Root cause #3 is the report's single most
   defensible claim and deserves to be #1.

5. **Complexity is omitted from the design matrix without justification.** The model uses only
   [N, D, N², ND] while pooling `low` + `medium`. Adding a complexity indicator: wall R² 0.089 → 0.093
   (LOCO 0.044 → 0.037, worse), computation 0.391 → 0.412 (LOCO 0.357 → 0.375). So the omission is
   **not** a significant driver — worth stating explicitly, as it eliminates an obvious alternative
   explanation. But it makes the comparison against the per-complexity historical fits structurally
   unfair, which should be disclosed.

6. **The 6 MAD outliers are identified and then ignored.** No exclusion, no sensitivity check. With
   n = 265 and R² = 0.089, six extreme wall-clock points can plausibly move the estimate.

7. **Minor — "Spot/OD mix".** 234 of 265 rows have tier literally `unknown`, not confirmed on-demand;
   the label implies tier is known for all rows.

8. **Minor — a near-degenerate statistic is listed as an effect size.** "Partial Pearson corr(wall, D/N |
   D,N) = −0.045" is uninformative by construction: D/N is a deterministic function of the controls, so
   linear residualisation leaves only nonlinearity. `metrics.json` also holds a rank-based version of the
   same quantity at **+0.069** — opposite sign — which the report does not surface.

---

## Verdict summary

| Check | Result |
|---|---|
| 1. Variance / ICC defined and plausible | **PARTIAL FAIL** — definitions correct; SPOT row degenerate and uncaveated; root-cause-#1 statistic understated ~2.3× |
| 2. `d < 0` for wall and computation | **PASS (arithmetic) / FAIL (inferential weight)** — signs reproduce exactly, but wall `d` is 47 % sign-unstable; concavity implication unstated |
| 3. Historical high-R² attribution evidenced by paths | **PARTIAL FAIL** — paths real and verified; metric unverified; aggregation mechanism (n=42) and `d` sign flip omitted; 2 of 4 fits (R²=1.0, 0.9999) silently filtered out |
| 4. Overclaim / missing caveat | **FAIL** — root-cause ranking contradicted by the 0.446 noise ceiling; verdict label is a hardcoded default; no-op screens and upstream survivorship undisclosed; no uncertainty |

**Required corrections before this report is used as evidence**

1. Replace within/total = 0.246 with the pooled 0.554 (η² 0.446, ICC 0.193); drop or flag the SPOT row.
2. Add the oracle cell-mean ceiling (R² = 0.446) and re-rank root causes: **metric mismatch and
   mean-surface misspecification above replicate noise**.
3. State that `d < 0` on both metrics contradicts the U-shape premise, and that wall `d` is
   indistinguishable from zero (95 % CI [−0.0082, +0.0070]).
4. Replace the hardcoded `partially_supported` with an evidence-derived verdict, or state plainly that
   the label is a default no test produced.
5. Rewrite §7 around `fitted_from_n_samples = 42` (aggregated, per-complexity) as the primary mechanism;
   drop the R² ≤ 0.95 cutoff and include the R² = 1.0 and 0.9999 fits; note the historical `d > 0` vs
   current `d < 0` sign flip; mark `metric_hint` as unverified.
6. Disclose that both data screens excluded nothing, that upstream failure filtering is unexamined, and
   that tier ≡ schema ≡ is_shifted are perfectly confounded.
7. Add bootstrap intervals to all headline R²/LOCO-R² values; state that Christos and Amdahl are
   indistinguishable on wall-clock.

**Retained as sound:** the entire data inventory, both variance formulas, all fitted coefficients and
R²/LOCO-R² values, the Spearman and partial-correlation figures, the MAD outlier count, the shape
classification counts (7/12 interior minima), and the central metric-mismatch conclusion — which the
bootstrap strengthens rather than weakens.

**Reproduction artifacts:** `tmp/paper2_rebuild/investigation/reviewer_check.py` (inventory, variance,
refits, oracle ceiling, aggregation test), `tmp/paper2_rebuild/investigation/reviewer_check2.py`
(600-resample cell-level bootstrap).
