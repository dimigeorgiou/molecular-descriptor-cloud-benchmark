# Paper 2 — Tasks 3–5 summary (N≤185 only)
Generated: `2026-09-16T23:56:22.410667+00:00`

## Scope
- Fitted on full_pipeline cells with N≤185, D∈{5…50}k, ≥3 reps.
- N>185 excluded from all fits (supplementary plot only).
- Coverage: `{"low": {"cells_present": 42, "cells_ge3": 42, "expected": 42, "hist": {"3": 33, "4": 9}}, "medium": {"cells_present": 42, "cells_ge3": 42, "expected": 42, "hist": {"3": 38, "4": 4}}}`
- Under-replicated excluded: 0 cells

## Task 3 — time models
- **low** winner=`a+b(D/N)+cN` R²=0.256 LOOCV-R²=0.160 AIC=395.0 quad_d>0=False
  emp argmin: `{'5000': {'N_emp_min': 50, 'T_median': 123.491}, '10000': {'N_emp_min': 75, 'T_median': 84.547}, '20000': {'N_emp_min': 75, 'T_median': 93.785}, '30000': {'N_emp_min': 25, 'T_median': 111.231}, '40000': {'N_emp_min': 25, 'T_median': 137.406}, '50000': {'N_emp_min': 25, 'T_median': 105.781}}`
  reversal flag: `{'N_at_D5000': 50, 'N_at_D50000': 25, 'reversal_persists': True, 'delta': -25}`
- **medium** winner=`a+b(D/N)+cN` R²=0.101 LOOCV-R²=-0.045 AIC=399.0 quad_d>0=True
  emp argmin: `{'5000': {'N_emp_min': 75, 'T_median': 98.234}, '10000': {'N_emp_min': 25, 'T_median': 139.681}, '20000': {'N_emp_min': 100, 'T_median': 194.528}, '30000': {'N_emp_min': 75, 'T_median': 160.907}, '40000': {'N_emp_min': 25, 'T_median': 142.603}, '50000': {'N_emp_min': 50, 'T_median': 84.576}}`
  reversal flag: `{'N_at_D5000': 75, 'N_at_D50000': 50, 'reversal_persists': True, 'delta': -25}`

## Task 4 — cost model
- Chosen: **flexible_log_linear** (cost_usd = rate_usd_per_node_hour * N * (wall_sec/3600))
- Rates: `{'on_demand': {'median_usd_per_node_hour': 0.00943419980349745, 'mean_usd_per_node_hour': 0.0237789111934989, 'std': 0.04006814860331487, 'n': 168}, 'spot': {'median_usd_per_node_hour': 0.0024169541466691454, 'mean_usd_per_node_hour': 0.008847943098861458, 'std': 0.014814038889304723, 'n': 854}}`
- RMSE analytical vs flexible: `{'analytical_rmse_usd': 0.014126776632797905, 'flexible_rmse_usd': 0.0079247011896446, 'flexible_coeffs': {'log_cost = a + b*log(N) + c*log(wall) + d*I_ondemand': {'a': -8.060073081969026, 'b': 0.08273947341823551, 'c': 0.5073479412445833, 'd': 1.4489600646129208}}, 'n_samples': 1022}`

## Task 5 — headline recommendations (w=0.5, Spot modeled)
- low D=5000: N*=25 T≈187.9s cost_spot_modeled≈$0.0032 (minT N=25, minCost N=25)
- low D=10000: N*=25 T≈179.9s cost_spot_modeled≈$0.0030 (minT N=25, minCost N=25)
- low D=20000: N*=25 T≈164.0s cost_spot_modeled≈$0.0028 (minT N=25, minCost N=25)
- low D=30000: N*=25 T≈148.0s cost_spot_modeled≈$0.0025 (minT N=25, minCost N=25)
- low D=40000: N*=25 T≈132.0s cost_spot_modeled≈$0.0022 (minT N=25, minCost N=25)
- low D=50000: N*=25 T≈116.1s cost_spot_modeled≈$0.0019 (minT N=25, minCost N=25)
- medium D=5000: N*=25 T≈204.2s cost_spot_modeled≈$0.0034 (minT N=25, minCost N=25)
- medium D=10000: N*=25 T≈207.9s cost_spot_modeled≈$0.0035 (minT N=25, minCost N=25)
- medium D=20000: N*=25 T≈215.4s cost_spot_modeled≈$0.0036 (minT N=25, minCost N=25)
- medium D=30000: N*=25 T≈222.8s cost_spot_modeled≈$0.0037 (minT N=25, minCost N=25)
- medium D=40000: N*=25 T≈230.2s cost_spot_modeled≈$0.0039 (minT N=25, minCost N=25)
- medium D=50000: N*=25 T≈237.7s cost_spot_modeled≈$0.0040 (minT N=25, minCost N=25)

## Figures
- `tmp/paper2_rebuild/figs/pareto_time_cost_low_nle185.pdf`
- `tmp/paper2_rebuild/figs/pareto_time_cost_medium_nle185.pdf`
- `tmp/paper2_rebuild/figs/supplementary_unreplicated_N_gt185.pdf` (unreplicated N>185 — not fitted)

## Files
- `tmp/paper2_rebuild/task3_time_models_nle185.json`
- `tmp/paper2_rebuild/task4_cost_model.json`
- `tmp/paper2_rebuild/task5_config_selector_table.json`
- `tmp/paper2_rebuild/config_selector.py`
