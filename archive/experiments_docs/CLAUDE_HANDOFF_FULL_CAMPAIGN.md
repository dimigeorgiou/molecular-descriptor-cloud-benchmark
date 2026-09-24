# Full Campaign Handoff — Chemoinformatics Descriptor Scaling

**Generated:** 2026-07-22 15:20 UTC
**Repository:** `chemoinformatics-descriptor-computation`
**Spreadsheet:** `1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs`
**Audience:** Claude / next analyst — full experiment history + current data state
**Decision:** Do **not** re-run N=128 for D=5k/10k (Spot/OD capacity failures). Treat as known gap.

**Related docs:**
- `experiments/docs/LATEST_EXPERIMENTS_HANDOFF.md` — earlier probe handoff
- `experiments/docs/CLAUDE_ANALYTICAL_HANDOFF_REP3.md` — mid-campaign analytical brief
- `tmp/probe_analysis_conclusions.md` — corrected narrative (no N*=16 plateau)
- `tmp/rep3_sheets_extract.json` — prior Sheets dump (may be stale)

---

## Part 0 — How to use

1. Read Part 1 (executive status) and Part 2 (scientific contract).
2. Use Part 3 timeline for what ran when.
3. Use Part 4–5 for Experiment IDs and coverage.
4. Use Part 6 pooled medians for analysis / refits.
5. Part 7 = conclusions & recommended paper claims.
6. Part 8 = open work (explicitly excludes N=128@5k/10k).

---

## Part 1 — Executive status

- **Rep3 Spot pow2 target grid:** OK=46/49 with ≥3 SUCCEEDED reps; PARTIAL=0; MISSING=3.
- **MISSING (accepted gap):** D=5k N=128 low, D=5k N=128 medium, D=10k N=128 medium.
- **Cause:** AWS Batch could not place 128-wide arrays (Spot and On-Demand): typically `n_children_started=0`, parent FAILED ~10s; occasional partial child failures.
- **N=128 at D=20k/40k:** SUCCEEDED earlier (usable).
- **Primary finding (unchanged):** scheduling fraction dominates wall time above N≈4–8; fitted N* grows with D but << paper 107–170; do not publish flat discrete-argmin N*=16 plateau.

### Coverage summary table
| D | Complexity | N with ≥3 reps | Gaps |
|---|------------|----------------|------|
| 5000 | low | [2, 4, 8, 16, 32, 64] | [128] |
| 5000 | medium | [2, 4, 8, 16, 32, 64] | [128] |
| 10000 | medium | [2, 4, 8, 16, 32, 64] | [128] |
| 20000 | low | [2, 4, 8, 16, 32, 64, 128] | — |
| 20000 | medium | [2, 4, 8, 16, 32, 64, 128] | — |
| 40000 | low | [2, 4, 8, 16, 32, 64, 128] | — |
| 40000 | medium | [2, 4, 8, 16, 32, 64, 128] | — |

---

## Part 2 — Scientific contract

| Metric | Use |
|--------|-----|
| Computation (s) | NOT for U-curves (monotone ↓ with N) |
| Scheduling (s) | Mechanism |
| Cluster Parallel (s) | Preferred U-curve clock |
| Wall Clock (s) | Alternate U-curve clock |
| Cost (USD) | Frontier only |

Merge rule: pool all SUCCEEDED `rep3_*` (+ resume/resume2/resume3) by `(D,N,complexity)`, then median.
Paper model: `T=a+bN+cD+dN²+eND`, `N*=-(b+eD)/(2d)` if d>0.

---

## Part 3 — Chronological campaign timeline

| When (approx) | What |
|---------------|------|
| ≤2026-07-09 | Paper replication low/medium compute_only grids; Sheets metric fixes |
| 2026-07-10–11 | Overnight full grid (N=25–185); partial stop on network/DNS |
| 2026-07-13–14 | Probes: D=10k low-N Spot; D=50k pow2 Spot/OD |
| 2026-07-14–16 | D=20k/40k pow2 Spot 1-rep; N=64/128 extension; analysis panels A–I |
| 2026-07-16 | Corrected “no N*=16 plateau”; 5-rep confirms for anomalies |
| 2026-07-16 11:56Z | **rep3 parallel** 7 Spot grids (3 reps, N=2..128) launched |
| 2026-07-16 14:40Z | All 7 FAIL — EndpointConnectionError (Batch/S3) mid-grid |
| 2026-07-17 | **resume** residual N — again EndpointConnectionError |
| 2026-07-22 | **resume2** (setsid/start_new_session) — filled most high-N |
| 2026-07-22 | **resume3** — filled remaining partials; N=128@5k/10k Spot FAILED |
| 2026-07-22 | Synced D=40k N=16 local SUCCEEDED → Sheets |
| 2026-07-22 | N=128 On-Demand retry — also FAILED (capacity/CE limits) |
| 2026-07-22 | **Decision: stop N=128@5k/10k; handoff for analysis** |

---

## Part 4 — Experiment ID catalog

### 4.1 Confirmations (5-rep anomalies)

| Experiment ID | SUCC | FAIL | Role |
|---------------|------|------|------|
| `confirm_d20k_n8_spot_medium` | 5 | 0 | scheduling-spike check |
| `confirm_d50k_n32_spot_low` | 5 | 0 | scheduling-spike check |

- `confirm_d20k_n8_spot_medium`: n=5 med_cp=81.465 med_sched=43.626 med_comp=37.901
- `confirm_d50k_n32_spot_low`: n=5 med_cp=127.303 med_sched=115.436 med_comp=12.308

### 4.2 Probe IDs

- `probe_d10k_low_n_spot`: SUCC=12 FAIL=0 rows=12
- `probe_d20k_d40k_pow2_spot_low`: SUCC=10 FAIL=0 rows=10
- `probe_d20k_d40k_pow2_spot_low_ext`: SUCC=4 FAIL=0 rows=4
- `probe_d20k_d40k_pow2_spot_medium`: SUCC=10 FAIL=0 rows=10
- `probe_d20k_d40k_pow2_spot_medium_ext`: SUCC=4 FAIL=0 rows=4
- `probe_d50k_pow2_ondemand`: SUCC=5 FAIL=0 rows=5
- `probe_d50k_pow2_ondemand_low`: SUCC=14 FAIL=0 rows=14
- `probe_d50k_pow2_ondemand_medium`: SUCC=14 FAIL=0 rows=14
- `probe_d50k_pow2_spot`: SUCC=4 FAIL=0 rows=4
- `probe_d50k_pow2_spot_low`: SUCC=14 FAIL=0 rows=14
- `probe_d50k_pow2_spot_medium`: SUCC=13 FAIL=1 rows=14

### 4.3 Rep3 family (including resumes)

| Experiment ID | SUCC | FAIL | rows |
|---------------|------|------|------|
| `rep3_d10k_n128_ondemand_medium` | 0 | 2 | 2 |
| `rep3_d10k_pow2_spot_medium` | 13 | 0 | 13 |
| `rep3_d10k_pow2_spot_medium_resume` | 1 | 0 | 1 |
| `rep3_d10k_pow2_spot_medium_resume2` | 5 | 3 | 9 |
| `rep3_d10k_pow2_spot_medium_resume3` | 0 | 2 | 2 |
| `rep3_d20k_pow2_spot_low` | 12 | 0 | 12 |
| `rep3_d20k_pow2_spot_low_resume` | 2 | 0 | 2 |
| `rep3_d20k_pow2_spot_low_resume2` | 7 | 0 | 9 |
| `rep3_d20k_pow2_spot_medium` | 11 | 0 | 11 |
| `rep3_d20k_pow2_spot_medium_resume` | 2 | 0 | 2 |
| `rep3_d20k_pow2_spot_medium_resume2` | 8 | 0 | 9 |
| `rep3_d20k_pow2_spot_medium_resume3` | 1 | 0 | 1 |
| `rep3_d40k_pow2_spot_low` | 9 | 0 | 9 |
| `rep3_d40k_pow2_spot_low_resume` | 1 | 0 | 1 |
| `rep3_d40k_pow2_spot_low_resume2` | 10 | 0 | 12 |
| `rep3_d40k_pow2_spot_low_resume3` | 1 | 0 | 1 |
| `rep3_d40k_pow2_spot_medium` | 9 | 0 | 9 |
| `rep3_d40k_pow2_spot_medium_resume` | 1 | 0 | 1 |
| `rep3_d40k_pow2_spot_medium_resume2` | 11 | 0 | 12 |
| `rep3_d5k_n128_ondemand_low` | 0 | 2 | 2 |
| `rep3_d5k_n128_ondemand_medium` | 0 | 3 | 3 |
| `rep3_d5k_pow2_spot_low` | 13 | 0 | 13 |
| `rep3_d5k_pow2_spot_low_resume` | 2 | 0 | 2 |
| `rep3_d5k_pow2_spot_low_resume2` | 3 | 3 | 6 |
| `rep3_d5k_pow2_spot_low_resume3` | 0 | 3 | 3 |
| `rep3_d5k_pow2_spot_medium` | 13 | 0 | 13 |
| `rep3_d5k_pow2_spot_medium_resume` | 2 | 0 | 2 |
| `rep3_d5k_pow2_spot_medium_resume2` | 2 | 3 | 6 |
| `rep3_d5k_pow2_spot_medium_resume3` | 3 | 3 | 6 |

### 4.4 Config YAML files

**rep3:**
- `experiments/configs/rep3_d10k_n128_ondemand_medium.yaml`
- `experiments/configs/rep3_d10k_pow2_spot_medium.yaml`
- `experiments/configs/rep3_d10k_pow2_spot_medium_resume.yaml`
- `experiments/configs/rep3_d10k_pow2_spot_medium_resume2.yaml`
- `experiments/configs/rep3_d10k_pow2_spot_medium_resume3.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_low.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_low_resume.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_low_resume2.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_medium.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_medium_resume.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_medium_resume2.yaml`
- `experiments/configs/rep3_d20k_pow2_spot_medium_resume3.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_low.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_low_resume.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_low_resume2.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_low_resume3.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_medium.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_medium_resume.yaml`
- `experiments/configs/rep3_d40k_pow2_spot_medium_resume2.yaml`
- `experiments/configs/rep3_d5k_n128_ondemand_low.yaml`
- `experiments/configs/rep3_d5k_n128_ondemand_medium.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_low.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_low_resume.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_low_resume2.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_low_resume3.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_medium.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_medium_resume.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_medium_resume2.yaml`
- `experiments/configs/rep3_d5k_pow2_spot_medium_resume3.yaml`

**confirm:**
- `experiments/configs/confirm_d20k_n8_spot_medium.yaml`
- `experiments/configs/confirm_d50k_n32_spot_low.yaml`

**probe (selected):**
- `experiments/configs/probe_d10k_low_n_spot.yaml`
- `experiments/configs/probe_d10k_low_n_spot_resume.yaml`
- `experiments/configs/probe_d20k_d40k_pow2_spot_low.yaml`
- `experiments/configs/probe_d20k_d40k_pow2_spot_low_ext.yaml`
- `experiments/configs/probe_d20k_d40k_pow2_spot_medium.yaml`
- `experiments/configs/probe_d20k_d40k_pow2_spot_medium_ext.yaml`
- `experiments/configs/probe_d50k_pow2_ondemand.yaml`
- `experiments/configs/probe_d50k_pow2_ondemand_low.yaml`
- `experiments/configs/probe_d50k_pow2_ondemand_medium.yaml`
- `experiments/configs/probe_d50k_pow2_ondemand_n32.yaml`
- `experiments/configs/probe_d50k_pow2_spot.yaml`
- `experiments/configs/probe_d50k_pow2_spot_low.yaml`
- `experiments/configs/probe_d50k_pow2_spot_medium.yaml`

---

## Part 5 — Logs & launchers

| Path | Role |
|------|------|
| `scripts/run_rep3_pow2_parallel.sh` | First parallel launch |
| `scripts/run_rep3_pow2_resume_parallel.sh` | Resume residual |
| `scripts/run_rep3_pow2_resume2_parallel.sh` | Resume2 residual |
| `tmp/rep3_pow2_parallel/` | First-pass logs |
| `tmp/rep3_pow2_resume/` | Resume logs |
| `tmp/rep3_pow2_resume2/` | Resume2 logs (start_new_session) |
| `tmp/rep3_pow2_resume3/` | Resume3 logs |
| `tmp/rep3_n128_ondemand/` | N=128 OD retry logs (failed) |
| `tmp/probe_analysis_panel.png` | Main 9-panel figure |
| `tmp/probe_analysis_conclusions.md` | Corrected conclusions |
| `tmp/nstar_fitted_vertices.json` | Fitted N* vertices |
| `scripts/plot_probe_analysis_panel.py` | Regenerate panels |

---

## Part 6 — Pooled medians (rep3 SUCCEEDED)

Format: med_cp / sched_frac (n_reps). `*` = n<3 provisional. `—` = missing.

| D | cx | N=2 | N=4 | N=8 | N=16 | N=32 | N=64 | N=128 | argmin N |
|---|----|----|----|----|-----|-----|-----|------|----------|
| 5000 | low | 49/24% | 61/69% | 46/77% | 51/89% | 62/96% | 107/98% | — | N=8 (46,n=3) |
| 5000 | medium | 68/46% | 46/58% | 60/83% | 47/87% | 72/97% | 96/98% | — | N=4 (46,n=3) |
| 10000 | medium | 111/34% | 64/42% | 85/77% | 51/79% | 91/94% | 79/96% | — | N=16 (51,n=3) |
| 20000 | low | 155/4% | 60/38% | 48/60% | 57/80% | 113/91% | 131/96% | 165/98% | N=8 (48,n=3) |
| 20000 | medium | 171/16% | 107/30% | 86/57% | 109/81% | 117/92% | 129/96% | 165/98% | N=8 (86,n=3) |
| 40000 | low | 291/0% | 156/4% | 169/51% | 90/80% | 101/90% | 152/96% | 171/98% | N=16 (90,n=3) |
| 40000 | medium | 295/0% | 165/10% | 159/53% | 96/80% | 93/89% | 147/96% | 182/98% | N=32 (93,n=3) |

### 6.1 Full pooled detail rows

| D | N | cx | n | med_cp | med_comp | med_sched | sched/cp | band | source eids |
|---|---|----|---|--------|----------|-----------|----------|------|-------------|
| 5000 | 2 | low | 3 | 49.147 | 36.301 | 11.722 | 0.239 | compute | `rep3_d5k_pow2_spot_low` |
| 5000 | 2 | medium | 3 | 68.34 | 36.247 | 31.18 | 0.456 | balanced | `rep3_d5k_pow2_spot_medium` |
| 5000 | 4 | low | 3 | 61.414 | 18.356 | 42.368 | 0.69 | sched | `rep3_d5k_pow2_spot_low` |
| 5000 | 4 | medium | 3 | 46.075 | 18.319 | 26.762 | 0.581 | balanced | `rep3_d5k_pow2_spot_medium` |
| 5000 | 8 | low | 3 | 45.889 | 9.209 | 35.394 | 0.771 | sched | `rep3_d5k_pow2_spot_low` |
| 5000 | 8 | medium | 3 | 60.104 | 9.229 | 49.889 | 0.83 | sched | `rep3_d5k_pow2_spot_medium` |
| 5000 | 16 | low | 3 | 51.495 | 4.971 | 45.989 | 0.893 | sched | `rep3_d5k_pow2_spot_low` |
| 5000 | 16 | medium | 3 | 47.493 | 5.008 | 41.379 | 0.871 | sched | `rep3_d5k_pow2_spot_medium` |
| 5000 | 32 | low | 3 | 61.806 | 2.489 | 59.493 | 0.963 | sched | `rep3_d5k_pow2_spot_low,rep3_d5k_pow2_spot_low_resume` |
| 5000 | 32 | medium | 3 | 71.81 | 2.293 | 69.577 | 0.969 | sched | `rep3_d5k_pow2_spot_medium,rep3_d5k_pow2_spot_medium_resume` |
| 5000 | 64 | low | 3 | 107.034 | 1.204 | 104.87 | 0.98 | sched | `rep3_d5k_pow2_spot_low_resume2` |
| 5000 | 64 | medium | 5 | 96.183 | 1.191 | 94.009 | 0.977 | sched | `rep3_d5k_pow2_spot_medium_resume2,rep3_d5k_pow2_spot_medium_resume3` |
| 10000 | 2 | medium | 3 | 111.066 | 72.374 | 37.515 | 0.338 | balanced | `rep3_d10k_pow2_spot_medium` |
| 10000 | 4 | medium | 3 | 64.132 | 36.696 | 27.13 | 0.423 | balanced | `rep3_d10k_pow2_spot_medium` |
| 10000 | 8 | medium | 3 | 85.169 | 18.499 | 65.591 | 0.77 | sched | `rep3_d10k_pow2_spot_medium` |
| 10000 | 16 | medium | 3 | 51.427 | 10.178 | 40.878 | 0.795 | sched | `rep3_d10k_pow2_spot_medium` |
| 10000 | 32 | medium | 4 | 90.709 | 4.707 | 85.411 | 0.942 | sched | `rep3_d10k_pow2_spot_medium,rep3_d10k_pow2_spot_medium_resume,rep3_d10k_pow2_spot_medium_resume2` |
| 10000 | 64 | medium | 3 | 78.742 | 2.429 | 75.921 | 0.964 | sched | `rep3_d10k_pow2_spot_medium_resume2` |
| 20000 | 2 | low | 3 | 155.313 | 145.489 | 5.518 | 0.036 | compute | `rep3_d20k_pow2_spot_low` |
| 20000 | 2 | medium | 3 | 171.415 | 144.671 | 27.027 | 0.158 | compute | `rep3_d20k_pow2_spot_medium` |
| 20000 | 4 | low | 3 | 59.839 | 36.49 | 22.688 | 0.379 | balanced | `rep3_d20k_pow2_spot_low` |
| 20000 | 4 | medium | 3 | 106.677 | 73.432 | 32.175 | 0.302 | compute | `rep3_d20k_pow2_spot_medium` |
| 20000 | 8 | low | 3 | 47.678 | 18.483 | 28.526 | 0.598 | balanced | `rep3_d20k_pow2_spot_low` |
| 20000 | 8 | medium | 3 | 85.754 | 39.355 | 48.908 | 0.57 | balanced | `rep3_d20k_pow2_spot_medium` |
| 20000 | 16 | low | 3 | 56.668 | 10.434 | 45.386 | 0.801 | sched | `rep3_d20k_pow2_spot_low` |
| 20000 | 16 | medium | 4 | 108.882 | 19.38 | 87.939 | 0.808 | sched | `rep3_d20k_pow2_spot_medium,rep3_d20k_pow2_spot_medium_resume` |
| 20000 | 32 | low | 3 | 113.454 | 5.202 | 103.548 | 0.913 | sched | `rep3_d20k_pow2_spot_low_resume,rep3_d20k_pow2_spot_low_resume2` |
| 20000 | 32 | medium | 3 | 116.71 | 9.215 | 106.925 | 0.916 | sched | `rep3_d20k_pow2_spot_medium_resume2,rep3_d20k_pow2_spot_medium_resume3` |
| 20000 | 64 | low | 3 | 130.562 | 4.802 | 125.387 | 0.96 | sched | `rep3_d20k_pow2_spot_low_resume2` |
| 20000 | 64 | medium | 3 | 129.192 | 4.818 | 123.647 | 0.957 | sched | `rep3_d20k_pow2_spot_medium_resume2` |
| 20000 | 128 | low | 3 | 165.388 | 2.477 | 161.826 | 0.978 | sched | `rep3_d20k_pow2_spot_low_resume2` |
| 20000 | 128 | medium | 3 | 165.346 | 2.48 | 162.113 | 0.98 | sched | `rep3_d20k_pow2_spot_medium_resume2` |
| 40000 | 2 | low | 3 | 290.602 | 291.025 | 0.068 | 0.0 | compute | `rep3_d40k_pow2_spot_low` |
| 40000 | 2 | medium | 3 | 294.821 | 291.649 | 0.672 | 0.002 | compute | `rep3_d40k_pow2_spot_medium` |
| 40000 | 4 | low | 3 | 156.013 | 146.975 | 6.487 | 0.042 | compute | `rep3_d40k_pow2_spot_low` |
| 40000 | 4 | medium | 3 | 164.65 | 146.987 | 17.276 | 0.105 | compute | `rep3_d40k_pow2_spot_medium` |
| 40000 | 8 | low | 3 | 168.614 | 80.262 | 86.559 | 0.513 | balanced | `rep3_d40k_pow2_spot_low` |
| 40000 | 8 | medium | 3 | 159.12 | 79.122 | 84.944 | 0.534 | balanced | `rep3_d40k_pow2_spot_medium` |
| 40000 | 16 | low | 3 | 90.329 | 18.495 | 72.503 | 0.803 | sched | `rep3_d40k_pow2_spot_low_resume,rep3_d40k_pow2_spot_low_resume2,rep3_d40k_pow2_spot_low_resume3` |
| 40000 | 16 | medium | 3 | 95.578 | 18.687 | 76.781 | 0.803 | sched | `rep3_d40k_pow2_spot_medium_resume,rep3_d40k_pow2_spot_medium_resume2` |
| 40000 | 32 | low | 3 | 101.366 | 9.556 | 91.502 | 0.903 | sched | `rep3_d40k_pow2_spot_low_resume2` |
| 40000 | 32 | medium | 3 | 92.8 | 9.511 | 82.896 | 0.893 | sched | `rep3_d40k_pow2_spot_medium_resume2` |
| 40000 | 64 | low | 3 | 151.574 | 4.768 | 145.875 | 0.962 | sched | `rep3_d40k_pow2_spot_low_resume2` |
| 40000 | 64 | medium | 3 | 147.262 | 4.875 | 141.348 | 0.96 | sched | `rep3_d40k_pow2_spot_medium_resume2` |
| 40000 | 128 | low | 3 | 171.13 | 2.449 | 167.565 | 0.979 | sched | `rep3_d40k_pow2_spot_low_resume2` |
| 40000 | 128 | medium | 3 | 182.011 | 4.594 | 178.405 | 0.98 | sched | `rep3_d40k_pow2_spot_medium_resume2` |

---

## Part 7 — Analytical conclusions for Claude

1. **Lead with scheduling fraction** (Panel I): ~50% by N≈4–8, >90% by N=32, ~98% at N=64–128 where data exist.
2. **Discrete argmins shift with D** (not a flat N=16 plateau): ~4–8 @5k, ~16 @10k med, ~8 @20k, ~32 @40k.
3. **Fitted global T(N,D)** should be refit on this 3-rep pooled table; expect N* growing with D, magnitude << paper.
4. **Do not publish** pow2-argmin plateau as physics.
5. **Anomalies:** confirm_d50k_n32_spot_low and confirm_d20k_n8_spot_medium show scheduling noise, not compute blowups.
6. **N=128 @5k/10k:** intentionally skipped after Spot+OD capacity failure — right arm already characterized at larger D and at N=64.
7. **Spot ≈ OD timing** (from earlier probes); Spot ~3× cheaper when comparable.

### Pre-rep3 optima excerpt
```json
{
  "spot_low_d50k": {
    "N": 16,
    "cluster_parallel": 105.7775,
    "computation": 23.332,
    "scheduling": 82.19800000000001,
    "cost": 0.009
  },
  "spot_med_d50k": {
    "N": 8,
    "cluster_parallel": 178.685,
    "computation": 92.1155,
    "scheduling": 90.4545,
    "cost": 0.01645
  },
  "spot_low_d20k": {
    "N": 16,
    "cluster_parallel": 43.371,
    "computation": 9.286,
    "scheduling": 32.781,
    "cost": 0.0039
  },
  "spot_low_d40k": {
    "N": 16,
    "cluster_parallel": 63.863,
    "computation": 18.684,
    "scheduling": 43.851,
    "cost": 0.0074
  },
  "spot_med_d20k": {
    "N": 16,
    "cluster_parallel": 64.224,
    "computation": 18.704,
    "scheduling": 45.188,
    "cost": 0.0072
  },
  "spot_med_d40k": {
    "N": 16,
    "cluster_parallel": 124.445,
    "computation": 37.555,
    "scheduling": 85.956,
    "cost": 0.0139
  },
  "od_low_d50k": {
    "N": 8,
    "cluster_parallel": 101.325,
    "computation": 47.297,
    "scheduling": 53.3335,
    "cost": 0.02795
  },
  "od_med_d50k": {
    "N": 32,
    "cluster_parallel": 187.998,
    "computation": 24.563499999999998,
    "scheduling": 163.18849999999998,
    "cost": 0.059
  },
  "spot_d10k": {
    "N": 5,
    "cluster_parallel": 17.325,
    "computation": 15.589,
    "scheduling": 1.146,
    "cost": 0.0018
  }
}
```

### Pre-rep3 fitted vertices
```json
{
  "local_fits": {
    "10000": {
      "a": 6.384236363636305,
      "b": 3.1786745454545575,
      "gamma": -0.023063636363636716,
      "r2": 0.8512189494890952,
      "N_raw": NaN,
      "N_clamp": 5,
      "N_argmin": 5,
      "T_min": 17.325
    },
    "20000": {
      "a": 70.8923576751119,
      "b": -0.6140818899593578,
      "gamma": 0.008856404336380455,
      "r2": 0.8886701940589883,
      "N_raw": 34.668803875452255,
      "N_clamp": 35,
      "N_argmin": 16,
      "T_min": 43.371
    },
    "40000": {
      "a": 95.26403527074025,
      "b": -0.06904389232840029,
      "gamma": 0.0032699094376594092,
      "r2": 0.27079456763920773,
      "N_raw": 10.557462468719269,
      "N_clamp": 11,
      "N_argmin": 16,
      "T_min": 63.863
    },
    "50000": {
      "a": 139.65634947839047,
      "b": 0.22492009467985324,
      "gamma": -0.0001719534150071341,
      "r2": 0.07984906890579868,
      "N_raw": NaN,
      "N_clamp": 16,
      "N_argmin": 16,
      "T_min": 105.7775
    }
  },
  "global": {
    "a": 11.331420938634906,
    "b": 0.3590274330845857,
    "c": 0.0024496485301808953,
    "d": 0.002937534734484406,
    "e": -1.02800936584366e-05,
    "r2": 0.7066311512229494,
    "Nstar": {
      "5000": -52.361417412549706,
      "10000": -43.61250498459082,
      "20000": -26.11468012867307,
      "30000": -8.616855272755311,
      "40000": 8.880969583162445,
      "50000": 26.378794439080192
    }
  }
}
```

---

## Part 8 — Open work (approved scope)

- [ ] Refit global `T(N,D)` on Part 6 pooled medians (exclude n<3 or mark provisional).
- [ ] Regenerate Panel E (fitted vs paper) and Panel I with rep3 data.
- [ ] Update `tmp/probe_analysis_conclusions.md` if numbers change materially.
- [ ] Optional: denser N near fitted vertex (e.g. 10–24) — **new campaign**, not N=128 retry.
- [x] **Out of scope:** further N=128 @ D=5k/10k (user decision 2026-07-22).

---

## Part 9 — Environment reproduce

```bash
cd chemoinformatics-descriptor-computation
source .env && export PYTHONPATH=.
conda activate venv_chemoinformatics
python scripts/plot_probe_analysis_panel.py
```

## Part 10 — Failure modes learned

1. Local orchestrator `EndpointConnectionError` to Batch/S3 kills mid-grid — use residual YAMLs + `start_new_session`.
2. Sheets upsert can fail even when Batch SUCCEEDED — re-upsert from `experiments/results/*/batch_compute_only_*.json`.
3. N=128 arrays need substantial CE capacity; parallel 3×128 exhausts placement (Spot and OD).
4. macOS has no `setsid`; use Python `subprocess.Popen(..., start_new_session=True)`.

## Part 11 — Per-row SUCCEEDED index (rep3 only)

`i | ExperimentID | D | N | cx | cp | wall | comp | sched | cost | status`

0001 | `rep3_d5k_pow2_spot_low` | 5000 | 2 | low | 49.147 | 259.731 | 36.202 | 11.722 | 0.0018 | SUCCEEDED
0002 | `rep3_d5k_pow2_spot_medium` | 5000 | 2 | medium | 68.34 | 290.642 | 36.146 | 31.18 | 0.0017 | SUCCEEDED
0003 | `rep3_d10k_pow2_spot_medium` | 10000 | 2 | medium | 117.658 | 339.956 | 73.326 | 43.04 | 0.0035 | SUCCEEDED
0004 | `rep3_d20k_pow2_spot_low` | 20000 | 2 | low | 155.313 | 441.494 | 148.558 | 5.518 | 0.0069 | SUCCEEDED
0005 | `rep3_d20k_pow2_spot_medium` | 20000 | 2 | medium | 494.871 | 746.437 | 145.393 | 348.36 | 0.0069 | SUCCEEDED
0006 | `rep3_d5k_pow2_spot_low` | 5000 | 2 | low | 43.362 | 520.599 | 36.301 | 6.167 | 0.0017 | SUCCEEDED
0007 | `rep3_d5k_pow2_spot_medium` | 5000 | 2 | medium | 121.714 | 525.561 | 36.247 | 84.262 | 0.0018 | SUCCEEDED
0008 | `rep3_d40k_pow2_spot_low` | 40000 | 2 | low | 290.498 | 882.051 | 289.309 | 0.003 | 0.0135 | SUCCEEDED
0009 | `rep3_d10k_pow2_spot_medium` | 10000 | 2 | medium | 111.066 | 560.044 | 72.374 | 37.515 | 0.0034 | SUCCEEDED
0010 | `rep3_d40k_pow2_spot_medium` | 40000 | 2 | medium | 292.856 | 974.846 | 291.649 | 0.002 | 0.0136 | SUCCEEDED
0011 | `rep3_d20k_pow2_spot_low` | 20000 | 2 | low | 165.195 | 571.784 | 143.368 | 20.844 | 0.0067 | SUCCEEDED
0012 | `rep3_d5k_pow2_spot_low` | 5000 | 2 | low | 143.78 | 230.605 | 36.619 | 105.866 | 0.0017 | SUCCEEDED
0013 | `rep3_d5k_pow2_spot_medium` | 5000 | 2 | medium | 59.382 | 222.012 | 36.619 | 22.508 | 0.0017 | SUCCEEDED
0014 | `rep3_d20k_pow2_spot_medium` | 20000 | 2 | medium | 171.415 | 315.09 | 144.642 | 27.027 | 0.0068 | SUCCEEDED
0015 | `rep3_d10k_pow2_spot_medium` | 10000 | 2 | medium | 78.099 | 217.324 | 72.312 | 5.006 | 0.0034 | SUCCEEDED
0016 | `rep3_d20k_pow2_spot_low` | 20000 | 2 | low | 147.036 | 229.829 | 145.489 | 0.372 | 0.0068 | SUCCEEDED
0017 | `rep3_d40k_pow2_spot_low` | 40000 | 2 | low | 290.602 | 424.114 | 291.025 | 0.068 | 0.0135 | SUCCEEDED
0018 | `rep3_d5k_pow2_spot_low` | 5000 | 4 | low | 61.414 | 283.503 | 18.292 | 42.368 | 0.0018 | SUCCEEDED
0019 | `rep3_d5k_pow2_spot_medium` | 5000 | 4 | medium | 52.056 | 274.572 | 18.292 | 32.621 | 0.0018 | SUCCEEDED
0020 | `rep3_d40k_pow2_spot_medium` | 40000 | 2 | medium | 330.744 | 360.391 | 291.025 | 43.779 | 0.0135 | SUCCEEDED
0021 | `rep3_d10k_pow2_spot_medium` | 10000 | 4 | medium | 64.132 | 255.194 | 36.586 | 27.13 | 0.0035 | SUCCEEDED
0022 | `rep3_d20k_pow2_spot_low` | 20000 | 4 | low | 59.839 | 138.741 | 36.123 | 22.688 | 0.0035 | SUCCEEDED
0023 | `rep3_d20k_pow2_spot_medium` | 20000 | 2 | medium | 162.159 | 398.618 | 144.671 | 16.408 | 0.0068 | SUCCEEDED
0024 | `rep3_d5k_pow2_spot_low` | 5000 | 4 | low | 63.386 | 125.38 | 18.429 | 43.81 | 0.0018 | SUCCEEDED
0025 | `rep3_d5k_pow2_spot_medium` | 5000 | 4 | medium | 36.088 | 134.826 | 18.319 | 16.705 | 0.0018 | SUCCEEDED
0026 | `rep3_d10k_pow2_spot_medium` | 10000 | 4 | medium | 81.326 | 161.789 | 36.929 | 43.734 | 0.0035 | SUCCEEDED
0027 | `rep3_d20k_pow2_spot_low` | 20000 | 4 | low | 80.071 | 206.987 | 36.496 | 43.094 | 0.0035 | SUCCEEDED
0028 | `rep3_d40k_pow2_spot_low` | 40000 | 2 | low | 302.959 | 387.727 | 293.801 | 10.95 | 0.0137 | SUCCEEDED
0029 | `rep3_d40k_pow2_spot_medium` | 40000 | 2 | medium | 294.821 | 411.26 | 293.701 | 0.672 | 0.0137 | SUCCEEDED
0030 | `rep3_d20k_pow2_spot_medium` | 20000 | 4 | medium | 123.138 | 297.735 | 73.487 | 49.123 | 0.0069 | SUCCEEDED
0031 | `rep3_d5k_pow2_spot_low` | 5000 | 4 | low | 57.096 | 305.051 | 18.356 | 37.609 | 0.0018 | SUCCEEDED
0032 | `rep3_d5k_pow2_spot_medium` | 5000 | 4 | medium | 46.075 | 301.897 | 18.356 | 26.762 | 0.0018 | SUCCEEDED
0033 | `rep3_d10k_pow2_spot_medium` | 10000 | 4 | medium | 55.547 | 243.371 | 36.696 | 17.644 | 0.0035 | SUCCEEDED
0034 | `rep3_d20k_pow2_spot_low` | 20000 | 4 | low | 54.072 | 168.119 | 36.49 | 16.37 | 0.0035 | SUCCEEDED
0035 | `rep3_d40k_pow2_spot_low` | 40000 | 4 | low | 153.414 | 262.441 | 145.73 | 6.474 | 0.0137 | SUCCEEDED
0036 | `rep3_d20k_pow2_spot_medium` | 20000 | 4 | medium | 94.807 | 275.605 | 73.036 | 22.075 | 0.0069 | SUCCEEDED
0037 | `rep3_d5k_pow2_spot_low` | 5000 | 8 | low | 45.889 | 306.382 | 9.229 | 35.394 | 0.0019 | SUCCEEDED
0038 | `rep3_d40k_pow2_spot_medium` | 40000 | 4 | medium | 274.091 | 340.104 | 145.503 | 127.857 | 0.0137 | SUCCEEDED
0039 | `rep3_d5k_pow2_spot_medium` | 5000 | 8 | medium | 43.186 | 324.545 | 9.229 | 32.876 | 0.0019 | SUCCEEDED
0040 | `rep3_d10k_pow2_spot_medium` | 10000 | 8 | medium | 47.589 | 331.882 | 18.354 | 28.023 | 0.0037 | SUCCEEDED
0041 | `rep3_d20k_pow2_spot_low` | 20000 | 8 | low | 47.678 | 327.542 | 18.218 | 28.526 | 0.0036 | SUCCEEDED
0042 | `rep3_d20k_pow2_spot_medium` | 20000 | 4 | medium | 106.677 | 521.24 | 73.432 | 32.175 | 0.0069 | SUCCEEDED
0043 | `rep3_d5k_pow2_spot_low` | 5000 | 8 | low | 84.409 | 504.279 | 9.145 | 74.155 | 0.0019 | SUCCEEDED
0044 | `rep3_d40k_pow2_spot_low` | 40000 | 4 | low | 265.237 | 659.84 | 146.975 | 117.476 | 0.0138 | SUCCEEDED
0045 | `rep3_d5k_pow2_spot_medium` | 5000 | 8 | medium | 91.617 | 566.121 | 9.24 | 81.393 | 0.0019 | SUCCEEDED
0046 | `rep3_d40k_pow2_spot_medium` | 40000 | 4 | medium | 164.65 | 628.219 | 146.987 | 17.276 | 0.0138 | SUCCEEDED
0047 | `rep3_d10k_pow2_spot_medium` | 10000 | 8 | medium | 85.169 | 590.473 | 18.499 | 65.591 | 0.0036 | SUCCEEDED
0048 | `rep3_d20k_pow2_spot_low` | 20000 | 8 | low | 41.685 | 593.723 | 18.483 | 22.279 | 0.0036 | SUCCEEDED
0049 | `rep3_d5k_pow2_spot_low` | 5000 | 8 | low | 38.306 | 239.679 | 9.209 | 28.099 | 0.0019 | SUCCEEDED
0050 | `rep3_d20k_pow2_spot_medium` | 20000 | 8 | medium | 85.293 | 248.061 | 36.775 | 48.908 | 0.007 | SUCCEEDED
0051 | `rep3_d5k_pow2_spot_medium` | 5000 | 8 | medium | 60.104 | 205.907 | 9.199 | 49.889 | 0.0019 | SUCCEEDED
0052 | `rep3_d10k_pow2_spot_medium` | 10000 | 8 | medium | 86.434 | 243.753 | 19.066 | 66.093 | 0.0037 | SUCCEEDED
0053 | `rep3_d40k_pow2_spot_low` | 40000 | 4 | low | 156.013 | 348.912 | 148.726 | 6.487 | 0.0139 | SUCCEEDED
0054 | `rep3_d20k_pow2_spot_low` | 20000 | 8 | low | 109.301 | 316.651 | 20.186 | 87.867 | 0.0037 | SUCCEEDED
0055 | `rep3_d40k_pow2_spot_medium` | 40000 | 4 | medium | 164.508 | 403.839 | 157.401 | 5.93 | 0.0142 | SUCCEEDED
0056 | `rep3_d5k_pow2_spot_low` | 5000 | 16 | low | 84.935 | 308.864 | 4.965 | 78.779 | 0.0022 | SUCCEEDED
0057 | `rep3_d20k_pow2_spot_medium` | 20000 | 8 | medium | 85.754 | 379.775 | 39.355 | 45.155 | 0.0073 | SUCCEEDED
0058 | `rep3_d5k_pow2_spot_medium` | 5000 | 16 | medium | 52.204 | 330.415 | 4.96 | 46.649 | 0.0022 | SUCCEEDED
0059 | `rep3_d10k_pow2_spot_medium` | 10000 | 16 | medium | 47.332 | 281.752 | 10 | 36.004 | 0.004 | SUCCEEDED
0060 | `rep3_d20k_pow2_spot_low` | 20000 | 16 | low | 80.12 | 326.044 | 10.497 | 68.512 | 0.0041 | SUCCEEDED
0061 | `rep3_d40k_pow2_spot_low` | 40000 | 8 | low | 168.614 | 438.359 | 80.828 | 86.559 | 0.0145 | SUCCEEDED
0062 | `rep3_d5k_pow2_spot_low` | 5000 | 16 | low | 51.495 | 387.469 | 5.036 | 45.989 | 0.0023 | SUCCEEDED
0063 | `rep3_d40k_pow2_spot_medium` | 40000 | 8 | medium | 162.403 | 401.209 | 80.31 | 87.39 | 0.0144 | SUCCEEDED
0064 | `rep3_d20k_pow2_spot_medium` | 20000 | 8 | medium | 88.214 | 399.585 | 39.666 | 50.381 | 0.0073 | SUCCEEDED
0065 | `rep3_d5k_pow2_spot_medium` | 5000 | 16 | medium | 47.493 | 393.016 | 5.008 | 41.379 | 0.0022 | SUCCEEDED
0066 | `rep3_d10k_pow2_spot_medium` | 10000 | 16 | medium | 57.362 | 400.113 | 10.193 | 46.037 | 0.0041 | SUCCEEDED
0067 | `rep3_d20k_pow2_spot_low` | 20000 | 16 | low | 46.573 | 285.389 | 10.434 | 36 | 0.004 | SUCCEEDED
0068 | `rep3_d5k_pow2_spot_low` | 5000 | 16 | low | 46.583 | 276.522 | 4.971 | 40.459 | 0.0022 | SUCCEEDED
0069 | `rep3_d40k_pow2_spot_low` | 40000 | 8 | low | 174.138 | 440.462 | 80.262 | 92.644 | 0.0147 | SUCCEEDED
0070 | `rep3_d40k_pow2_spot_medium` | 40000 | 8 | medium | 155.401 | 428.854 | 79.122 | 80.222 | 0.0143 | SUCCEEDED
0071 | `rep3_d20k_pow2_spot_medium` | 20000 | 16 | medium | 114.194 | 397.499 | 20.14 | 93.109 | 0.0076 | SUCCEEDED
0072 | `rep3_d5k_pow2_spot_medium` | 5000 | 16 | medium | 46.594 | 400.547 | 5.119 | 40.279 | 0.0023 | SUCCEEDED
0073 | `rep3_d10k_pow2_spot_medium` | 10000 | 16 | medium | 51.427 | 399.066 | 10.178 | 40.878 | 0.004 | SUCCEEDED
0074 | `rep3_d20k_pow2_spot_low` | 20000 | 16 | low | 56.668 | 413.962 | 9.952 | 45.386 | 0.0041 | SUCCEEDED
0075 | `rep3_d5k_pow2_spot_low` | 5000 | 32 | low | 40.105 | 322.797 | 2.518 | 36.404 | 0.0028 | SUCCEEDED
0076 | `rep3_d40k_pow2_spot_low` | 40000 | 8 | low | 160.189 | 436.925 | 78.097 | 84.42 | 0.0143 | SUCCEEDED
0077 | `rep3_d40k_pow2_spot_medium` | 40000 | 8 | medium | 159.12 | 406.338 | 74.759 | 84.944 | 0.014 | SUCCEEDED
0078 | `rep3_d20k_pow2_spot_medium` | 20000 | 16 | medium | 119.487 | 398.176 | 18.49 | 100.337 | 0.0072 | SUCCEEDED
0079 | `rep3_d5k_pow2_spot_medium` | 5000 | 32 | medium | 46.75 | 407.951 | 2.363 | 43.372 | 0.0026 | SUCCEEDED
0080 | `rep3_d10k_pow2_spot_medium` | 10000 | 32 | medium | 65.147 | 424.721 | 4.694 | 59.417 | 0.0043 | SUCCEEDED
0081 | `rep3_d20k_pow2_spot_medium_resume` | 20000 | 16 | medium | 103.57 | 381.479 | 19.63 | 82.77 | 0.0074 | SUCCEEDED
0082 | `rep3_d5k_pow2_spot_medium_resume` | 5000 | 32 | medium | 76.543 | 435.336 | 2.293 | 74.251 | 0.0019 | SUCCEEDED
0083 | `rep3_d20k_pow2_spot_low_resume` | 20000 | 32 | low | 98.737 | 526.201 | 5.202 | 92.987 | 0.0045 | SUCCEEDED
0084 | `rep3_d5k_pow2_spot_low_resume` | 5000 | 32 | low | 61.806 | 578.289 | 2.489 | 59.493 | 0.0019 | SUCCEEDED
0085 | `rep3_d10k_pow2_spot_medium_resume` | 10000 | 32 | medium | 97.371 | 667.678 | 4.962 | 91.9 | 0.0045 | SUCCEEDED
0086 | `rep3_d40k_pow2_spot_low_resume` | 40000 | 16 | low | 166.67 | 802.27 | 39.033 | 128.926 | 0.0142 | SUCCEEDED
0087 | `rep3_d40k_pow2_spot_medium_resume` | 40000 | 16 | medium | 158.152 | 924.347 | 39.387 | 120.535 | 0.0141 | SUCCEEDED
0088 | `rep3_d20k_pow2_spot_medium_resume` | 20000 | 16 | medium | 87.75 | 581.133 | 19.13 | 68.285 | 0.0073 | SUCCEEDED
0089 | `rep3_d5k_pow2_spot_medium_resume` | 5000 | 32 | medium | 71.81 | 593.573 | 1.187 | 69.577 | 0.0018 | SUCCEEDED
0090 | `rep3_d20k_pow2_spot_low_resume` | 20000 | 32 | low | 162.998 | 675.282 | 4.501 | 157.657 | 0.004 | SUCCEEDED
0091 | `rep3_d5k_pow2_spot_low_resume` | 5000 | 32 | low | 78.654 | 690.537 | 1.125 | 76.36 | 0.0016 | SUCCEEDED
0092 | `rep3_d5k_pow2_spot_low_resume2` | 5000 | 64 | low | 107.034 | 833.459 | 1.161 | 104.87 | 0.0033 | SUCCEEDED
0093 | `rep3_d5k_pow2_spot_medium_resume2` | 5000 | 64 | medium | 96.183 | 924.553 | 1.156 | 94.009 | 0.0033 | SUCCEEDED
0094 | `rep3_d5k_pow2_spot_low_resume2` | 5000 | 64 | low | 123.369 | 775.653 | 1.204 | 121.797 | 0.0033 | SUCCEEDED
0095 | `rep3_d10k_pow2_spot_medium_resume2` | 10000 | 32 | medium | 87.6 | 789.236 | 4.616 | 82.394 | 0.0041 | SUCCEEDED
0096 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 16 | medium | 95.578 | 877.54 | 18.175 | 76.781 | 0.0069 | SUCCEEDED
0097 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 32 | medium | 95.335 | 963.399 | 4.657 | 89.81 | 0.0041 | SUCCEEDED
0098 | `rep3_d5k_pow2_spot_low_resume2` | 5000 | 64 | low | 97.34 | 604.683 | 1.217 | 95.063 | 0.0033 | SUCCEEDED
0099 | `rep3_d10k_pow2_spot_medium_resume2` | 10000 | 32 | medium | 93.818 | 605.979 | 4.721 | 88.428 | 0.0041 | SUCCEEDED
0100 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 16 | medium | 89.308 | 603.779 | 18.687 | 71.14 | 0.007 | SUCCEEDED
0101 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 16 | low | 90.329 | 667.177 | 18.495 | 72.503 | 0.007 | SUCCEEDED
0102 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 32 | low | 113.454 | 775.957 | 9.249 | 103.548 | 0.0074 | SUCCEEDED
0103 | `rep3_d5k_pow2_spot_medium_resume2` | 5000 | 64 | medium | 111.578 | 869.575 | 1.168 | 109.438 | 0.0033 | SUCCEEDED
0104 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 32 | medium | 116.71 | 923.051 | 9.215 | 106.925 | 0.0074 | SUCCEEDED
0105 | `rep3_d10k_pow2_spot_medium_resume2` | 10000 | 64 | medium | 102.98 | 757.308 | 2.334 | 100.344 | 0.0049 | SUCCEEDED
0106 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 32 | medium | 112.925 | 772.535 | 9.126 | 103.437 | 0.0074 | SUCCEEDED
0107 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 32 | low | 204.391 | 875.255 | 9.49 | 193.802 | 0.0075 | SUCCEEDED
0108 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 64 | low | 130.562 | 878.509 | 4.797 | 125.387 | 0.0089 | SUCCEEDED
0109 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 64 | medium | 129.192 | 933.704 | 4.789 | 123.647 | 0.0089 | SUCCEEDED
0110 | `rep3_d10k_pow2_spot_medium_resume2` | 10000 | 64 | medium | 74.013 | 852.885 | 2.429 | 71.008 | 0.0055 | SUCCEEDED
0111 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 32 | medium | 86.293 | 831.493 | 9.511 | 75.611 | 0.0078 | SUCCEEDED
0112 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 32 | low | 86.058 | 733.988 | 9.556 | 75.488 | 0.0079 | SUCCEEDED
0113 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 64 | low | 129.957 | 729.22 | 4.844 | 123.953 | 0.0089 | SUCCEEDED
0114 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 64 | medium | 130.149 | 734.093 | 4.818 | 124.992 | 0.0089 | SUCCEEDED
0115 | `rep3_d10k_pow2_spot_medium_resume2` | 10000 | 64 | medium | 78.742 | 731.153 | 2.435 | 75.921 | 0.0055 | SUCCEEDED
0116 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 32 | medium | 92.8 | 743.974 | 9.631 | 82.896 | 0.0077 | SUCCEEDED
0117 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 32 | low | 101.366 | 737.225 | 9.603 | 91.502 | 0.0077 | SUCCEEDED
0118 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 64 | low | 136.466 | 732.689 | 4.802 | 131.151 | 0.0088 | SUCCEEDED
0119 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 64 | medium | 125.346 | 727.573 | 4.836 | 119.399 | 0.0089 | SUCCEEDED
0120 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 64 | medium | 124.073 | 689.798 | 4.833 | 117.864 | 0.0088 | SUCCEEDED
0121 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 64 | low | 134.592 | 743.369 | 4.768 | 128.787 | 0.0088 | SUCCEEDED
0122 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 128 | low | 149.637 | 758.178 | 2.447 | 146.981 | 0.011 | SUCCEEDED
0123 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 128 | medium | 142.648 | 636.77 | 2.408 | 139.259 | 0.0109 | SUCCEEDED
0124 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 64 | medium | 163.664 | 781.095 | 4.93 | 157.932 | 0.0086 | SUCCEEDED
0125 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 64 | low | 151.574 | 787.574 | 4.856 | 145.875 | 0.0086 | SUCCEEDED
0126 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 128 | low | 170.921 | 813.243 | 2.478 | 168.896 | 0.0106 | SUCCEEDED
0127 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 128 | medium | 165.346 | 831.772 | 2.486 | 162.113 | 0.0106 | SUCCEEDED
0128 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 64 | medium | 147.262 | 740.439 | 4.875 | 141.348 | 0.0086 | SUCCEEDED
0129 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 64 | low | 154.487 | 751.315 | 4.604 | 148.735 | 0.0086 | SUCCEEDED
0130 | `rep3_d20k_pow2_spot_low_resume2` | 20000 | 128 | low | 165.388 | 750.877 | 2.477 | 161.826 | 0.0107 | SUCCEEDED
0131 | `rep3_d20k_pow2_spot_medium_resume2` | 20000 | 128 | medium | 166.045 | 750.908 | 2.48 | 162.469 | 0.0106 | SUCCEEDED
0132 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 128 | medium | 172.653 | 612.843 | 2.476 | 168.845 | 0.0106 | SUCCEEDED
0133 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 128 | low | 166.769 | 628.472 | 2.442 | 163.379 | 0.0106 | SUCCEEDED
0134 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 128 | medium | 183.268 | 314.032 | 4.594 | 179.901 | 0.0113 | SUCCEEDED
0135 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 128 | low | 172.69 | 315.515 | 2.449 | 169.584 | 0.0107 | SUCCEEDED
0136 | `rep3_d40k_pow2_spot_medium_resume2` | 40000 | 128 | medium | 182.011 | 313.782 | 4.667 | 178.405 | 0.0113 | SUCCEEDED
0137 | `rep3_d40k_pow2_spot_low_resume2` | 40000 | 128 | low | 171.13 | 319.129 | 2.463 | 167.565 | 0.0106 | SUCCEEDED
0138 | `rep3_d5k_pow2_spot_medium_resume3` | 5000 | 64 | medium | 256.226 | 467.664 | 1.191 | 253.731 | 0.0033 | SUCCEEDED
0139 | `rep3_d20k_pow2_spot_medium_resume3` | 20000 | 32 | medium | 130.31 | 565.39 | 9.382 | 119.927 | 0.0077 | SUCCEEDED
0140 | `rep3_d5k_pow2_spot_medium_resume3` | 5000 | 64 | medium | 87.879 | 581.736 | 1.218 | 86.455 | 0.0035 | SUCCEEDED
0141 | `rep3_d5k_pow2_spot_medium_resume3` | 5000 | 64 | medium | 84.757 | 375.012 | 1.275 | 82.431 | 0.0036 | SUCCEEDED
0142 | `rep3_d40k_pow2_spot_low_resume3` | 40000 | 16 | low | 89.042 | 979.535 | 18.124 | 70.353 | 0.007 | SUCCEEDED

Total rep3 SUCCEEDED rows indexed: 142

## Part 11b — Corrected conclusions (verbatim)

```markdown
# Probe analysis — corrected summary (2026-07-16)

**Generated by:** `scripts/plot_probe_analysis_panel.py`  
**Status:** Panel E narrative corrected — do **not** publish “N*=16 plateau”.

---

## Visualization links

| # | Figure | Absolute path |
|---|--------|----------------|
| 1 | **Main 9-panel (A–I)** | `/Users/dimitriosgeorgiou/Desktop/git/chemoinformatics-descriptor-computation/tmp/probe_analysis_panel.png` |
| 2 | **Extra 3-panel (J–L)** | `/Users/dimitriosgeorgiou/Desktop/git/chemoinformatics-descriptor-computation/tmp/probe_analysis_panel_extra.png` |
| 3 | **Stacked decomp** | `/Users/dimitriosgeorgiou/Desktop/git/chemoinformatics-descriptor-computation/tmp/probe_analysis_decomposition.png` |

```bash
open tmp/probe_analysis_panel.png
```

## Analysis docs

| Doc | Path |
|-----|------|
| **This summary** | `tmp/probe_analysis_conclusions.md` |
| **Numeric JSON** | `tmp/probe_analysis_summary.json` |
| **Fitted vertices** | `tmp/nstar_fitted_vertices.json` |
| **N* math (paper)** | `tmp/nstar_math_analysis.md` |
| **Experiment handoff** | `experiments/docs/LATEST_EXPERIMENTS_HANDOFF.md` |

---

## What the figure actually supports (corrected)

### ★ Panel I — strongest, most defensible finding

Scheduling-fraction-of-wall-time (`sched / cluster_parallel`):

- Crosses **~50% by N≈4–8** for D=20k / 40k / 50k
- Converges to **>90% by N=32**

This is a **direct ratio** — no fitted vertex, no argmin. Orchestration dominates almost immediately, not only “at high N.” **Lead with Panel I in the paper.**

### Panel E — argmin fallacy (do not publish flat plateau)

| D | Discrete argmin (pow2) | Per-D quadratic N* | Global T(N,D) N* | Paper N* |
|---|------------------------|--------------------|------------------|----------|
| 10k | 5 | non-convex (γ≤0) | clamped low | 114 |
| 20k | **16** | **~35** | grows with D | 128 |
| 40k | **16** | **~11** | ~9 | 156 |
| 50k | **16** | non-convex (N=32 spike) | **~26** | 170 |

Connecting discrete argmins (2,4,8,16,32,…) produces a **false flat “N*=16 plateau”**. That is a **sampling-grid artifact**, not a physical vertex.

**Publish instead:** fitted vertices from global `T(N,D)` (and/or per-D quadratic when γ>0). Direction matches the paper (N* increases with D); **magnitude is far smaller** than paper’s 107–170.

### Panels C/D — known anomalies (scheduling, not compute)

| Cell | What it looks like | Mechanism | Action |
|------|-------------------|-----------|--------|
| D=50k Spot low **N=32** | green spike in Panel C | sched≈173 s, comp≈12 s | **5-rep** `confirm_d50k_n32_spot_low` |
| D=20k Spot medium **N=8** | orange dip oddity in Panel D | sched≈120 s, comp≈37 s | **5-rep** `confirm_d20k_n8_spot_medium` |

Neither is a compute blowup. Do not put this figure in a final paper until those reps land.

---

## Panel map

| Panel | Content | Paper role |
|-------|---------|------------|
| A | D=50k Spot low vs medium | supporting |
| B | Spot vs OD timing | supporting |
| C | Multi-D Spot low U-curves | supporting (flag N=32) |
| D | Multi-D Spot medium U-curves | supporting (flag N=8 @20k) |
| E | N* vs D — **fitted vs argmin vs paper** | use fitted only |
| F | Wall time at discrete N* vs D | secondary |
| G | Compute vs scheduling bars | supports I |
| H | Cost frontier Spot vs OD | cost claim |
| **I** | **Scheduling fraction vs N** | **primary mechanism** |

---

## Verdict (updated)

1. **Mechanism (publish):** scheduling/orchestration dominates wall time above N≈4–8 (Panel I).
2. **N*(D) (publish carefully):** fitted global model shows N* **increasing with D**, correcting paper magnitude; **do not** claim a flat N*=16 plateau from discrete argmins.
3. **Spot ≈ OD** timing; Spot ~3× cheaper (Panel H).
4. **Blockers before final figures:** 5-rep confirmation on the two scheduling spikes.

---

## Regenerate

```bash
source .env && export PYTHONPATH=.
python scripts/plot_probe_analysis_panel.py
```
```

## Part 11c — Paper fitted model

```json
{
  "a": 264.34783884803187,
  "b": -4.044640277777702,
  "c": 0.012341664750445583,
  "d": 0.020314632352941175,
  "e": -5.7162670825905844e-05,
  "r_squared": 0.8508869958443468,
  "fitted_from_n_samples": 170,
  "source": "paper_fitted"
}
```

## Part 11d — Local result directories (rep3*)

- `experiments/results/rep3_d10k_n128_ondemand_medium_20260722_141021`
- `experiments/results/rep3_d10k_pow2_spot_medium_20260716_115636`
- `experiments/results/rep3_d10k_pow2_spot_medium_resume2_20260721_232746`
- `experiments/results/rep3_d10k_pow2_spot_medium_resume2_20260721_235143`
- `experiments/results/rep3_d10k_pow2_spot_medium_resume2_20260721_235441`
- `experiments/results/rep3_d10k_pow2_spot_medium_resume3_20260722_105439`
- `experiments/results/rep3_d10k_pow2_spot_medium_resume_20260717_111723`
- `experiments/results/rep3_d20k_pow2_spot_low_20260716_115644`
- `experiments/results/rep3_d20k_pow2_spot_low_resume2_20260721_232754`
- `experiments/results/rep3_d20k_pow2_spot_low_resume2_20260721_235147`
- `experiments/results/rep3_d20k_pow2_spot_low_resume2_20260721_235445`
- `experiments/results/rep3_d20k_pow2_spot_low_resume_20260717_111731`
- `experiments/results/rep3_d20k_pow2_spot_medium_20260716_115652`
- `experiments/results/rep3_d20k_pow2_spot_medium_resume2_20260721_232802`
- `experiments/results/rep3_d20k_pow2_spot_medium_resume2_20260721_235152`
- `experiments/results/rep3_d20k_pow2_spot_medium_resume2_20260721_235449`
- `experiments/results/rep3_d20k_pow2_spot_medium_resume3_20260722_105444`
- `experiments/results/rep3_d20k_pow2_spot_medium_resume_20260717_111740`
- `experiments/results/rep3_d40k_pow2_spot_low_20260716_115700`
- `experiments/results/rep3_d40k_pow2_spot_low_resume2_20260721_232810`
- `experiments/results/rep3_d40k_pow2_spot_low_resume2_20260721_235157`
- `experiments/results/rep3_d40k_pow2_spot_low_resume2_20260721_235453`
- `experiments/results/rep3_d40k_pow2_spot_low_resume3_20260722_105449`
- `experiments/results/rep3_d40k_pow2_spot_low_resume_20260717_111747`
- `experiments/results/rep3_d40k_pow2_spot_medium_20260716_115708`
- `experiments/results/rep3_d40k_pow2_spot_medium_resume2_20260721_232818`
- `experiments/results/rep3_d40k_pow2_spot_medium_resume2_20260721_235202`
- `experiments/results/rep3_d40k_pow2_spot_medium_resume2_20260721_235457`
- `experiments/results/rep3_d40k_pow2_spot_medium_resume_20260717_111756`
- `experiments/results/rep3_d5k_n128_ondemand_low_20260722_141010`
- `experiments/results/rep3_d5k_n128_ondemand_medium_20260722_141015`
- `experiments/results/rep3_d5k_pow2_spot_low_20260716_115629`
- `experiments/results/rep3_d5k_pow2_spot_low_resume2_20260721_232731`
- `experiments/results/rep3_d5k_pow2_spot_low_resume2_20260721_235135`
- `experiments/results/rep3_d5k_pow2_spot_low_resume2_20260721_235433`
- `experiments/results/rep3_d5k_pow2_spot_low_resume3_20260722_105430`
- `experiments/results/rep3_d5k_pow2_spot_low_resume_20260717_111718`
- `experiments/results/rep3_d5k_pow2_spot_medium_20260716_115629`
- `experiments/results/rep3_d5k_pow2_spot_medium_resume2_20260721_232738`
- `experiments/results/rep3_d5k_pow2_spot_medium_resume2_20260721_235137`
- `experiments/results/rep3_d5k_pow2_spot_medium_resume2_20260721_235437`
- `experiments/results/rep3_d5k_pow2_spot_medium_resume3_20260722_105434`
- `experiments/results/rep3_d5k_pow2_spot_medium_resume_20260717_111718`

## Part 12 — Closing

This handoff supersedes mid-flight docs for **campaign inventory + current Sheets state**.
For deep pre-rep3 probe narrative see `LATEST_EXPERIMENTS_HANDOFF.md`.
Generated 2026-07-22T15:20:21.627501+00:00.

