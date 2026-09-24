# Task 3 — medians vs raw-row refit
Generated: `2026-09-17T00:03:27.566837+00:00`

## Diagnosis
- **Prior Task 3 fit unit: per-cell medians** (`n_cells=42` per tier).
- Code: `pool_cells()` → `np.median(vals)` then `evaluate_models`.
- Hypothesis confirmed: weak R²/LOOCV was measured on 42 aggregated points, not raw rows.

## Raw-row refit (same model zoo, N≤185, ≥3-rep cells)
- Primary selection metric: **leave-one-cell-out R²** (predict held-out (D,N) cells).
- Also report row-wise LOOCV (can look optimistic because replicates share (D,N)).

### low
- Prior (medians, n=42): winner=`a+b(D/N)+cN` R²=0.256 LOOCV-R²=0.160
- Raw rows: n_rows=135 n_cells=42; winner_by_cell_LOOCV=`a+b(D/N)+c*sqrt(N)`
  - in-sample R²=0.106; row-LOOCV R²=0.072; **cell-LOOCV R²=0.065**; AIC=1343.2
- Predicted N* at boundary N=25 for 6/6 D values (winner coeffs).
- Emp argmin (cell medians): `{'5000': {'N_emp_min': 50, 'T_median': 123.491}, '10000': {'N_emp_min': 75, 'T_median': 84.547}, '20000': {'N_emp_min': 75, 'T_median': 93.785}, '30000': {'N_emp_min': 25, 'T_median': 111.231}, '40000': {'N_emp_min': 25, 'T_median': 137.406}, '50000': {'N_emp_min': 25, 'T_median': 105.781}}`
- Reversal flag: `{'N_at_D5000': 50, 'N_at_D50000': 25, 'delta': -25, 'reversal_persists': True}`

| model | R² | row-LOOCV | cell-LOOCV | AIC |
|---|---:|---:|---:|---:|
| `a+b(D/N)+c*sqrt(N)` | 0.106 | 0.072 | 0.065 | 1343.2 |
| `a+b(D/N)+c*log(N)` | 0.104 | 0.070 | 0.065 | 1343.5 |
| `a+b(D/N)+cN` | 0.104 | 0.070 | 0.062 | 1343.5 |
| `a+b(D/N)+cN+dN^2` | 0.107 | 0.058 | 0.048 | 1345.1 |
| `quadratic` | 0.109 | 0.042 | 0.024 | 1346.8 |

### medium
- Prior (medians, n=42): winner=`a+b(D/N)+cN` R²=0.101 LOOCV-R²=-0.045
- Raw rows: n_rows=130 n_cells=42; winner_by_cell_LOOCV=`a+b(D/N)+cN`
  - in-sample R²=0.079; row-LOOCV R²=0.036; **cell-LOOCV R²=0.019**; AIC=1304.2
- Predicted N* at boundary N=25 for 6/6 D values (winner coeffs).
- Emp argmin (cell medians): `{'5000': {'N_emp_min': 75, 'T_median': 98.234}, '10000': {'N_emp_min': 25, 'T_median': 139.681}, '20000': {'N_emp_min': 100, 'T_median': 194.528}, '30000': {'N_emp_min': 75, 'T_median': 160.907}, '40000': {'N_emp_min': 25, 'T_median': 142.603}, '50000': {'N_emp_min': 50, 'T_median': 84.576}}`
- Reversal flag: `{'N_at_D5000': 75, 'N_at_D50000': 50, 'delta': -25, 'reversal_persists': True}`

| model | R² | row-LOOCV | cell-LOOCV | AIC |
|---|---:|---:|---:|---:|
| `a+b(D/N)+cN` | 0.079 | 0.036 | 0.019 | 1304.2 |
| `a+b(D/N)+c*sqrt(N)` | 0.071 | 0.028 | 0.007 | 1305.3 |
| `a+b(D/N)+cN+dN^2` | 0.086 | 0.027 | -0.002 | 1305.1 |
| `a+b(D/N)+c*log(N)` | 0.059 | 0.016 | -0.011 | 1306.9 |
| `quadratic` | 0.092 | 0.012 | -0.028 | 1306.3 |

## Manuscript recommendation
- `{
  "do_not_quote_Nstar_from_parametric_fit": true,
  "preferred_framing": "no interior time-minimizing configuration in tested N=25..185; smallest tested N at/near optimal; scheduling overhead dominates",
  "use_task4_cost_model": true,
  "use_task1_od_spot_ratio_3_20": true,
  "note": "If cell-LOOCV R\u00b2 stays near zero/negative after raw-row refit, put negative/weak LOOCV in Limitations; do not publish N* table from the fit."
}`
