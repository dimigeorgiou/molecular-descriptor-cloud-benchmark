# Latest Experiments Handoff — Probe & Scaling Analysis

**Generated:** 2026-07-14  
**Repository:** `chemoinformatics-descriptor-computation`  
**Audience:** Next analyst / Claude / thesis extension — continue figures, model refit, paper updates  
**Spreadsheet ID:** `1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs`  
**Prior handoff:** `experiments/docs/HANDOFF_CLAUDE.md` (full replication narrative through 2026-07-09)

---

## Part 0 — How to use this document

1. Read **Part 1** (executive summary) and **Part 4** (key findings).
2. Use **Part 2** (experiment catalog) to pull exact rows from Google Sheets by `Experiment ID`.
3. Use **Part 5** (artifacts index) for plots, JSON, logs, and scripts.
4. Use **Part 6** (N* math) when connecting to the paper’s analytical model.
5. Execute **Part 7** (open work) for the next analysis session.

**Filter rule for U-curve plots:** `Status=SUCCEEDED`, metric = **`Wall Clock (s)`** or **`Cluster Parallel (s)`** — **not** `Computation (s)` alone.

---

## Part 1 — Executive summary

Between **2026-07-10** and **2026-07-14** we ran a focused **low-N probe campaign** to locate the U-curve minimum for descriptor scaling on AWS Batch, after the overnight full grid (N=25–185) showed minima near N=25 but could not see N &lt; 25.

### What succeeded

| Campaign | Status | Main result |
|----------|--------|-------------|
| **D=10k low-N Spot probe** | ✅ Complete | Optimum **N=5**, ~17 s cluster_parallel |
| **D=50k pow2 Spot (1-rep)** | ✅ Complete | U-shape; min ~N=8–16 |
| **D=50k pow2 OD (1-rep, N≤32)** | ✅ Complete | Spot ≈ OD timing |
| **D=50k pow2 Spot low+medium (2-rep)** | ✅ Complete | 28 cells; min N=16 low, N=8 medium |
| **D=50k pow2 OD low+medium (2-rep)** | ✅ Complete | 28 cells; min N=8 low, N=32 medium |
| **Analysis panel + N* audit** | ✅ Complete | Figures + `nstar_math_analysis.md` |
| **N=1 Batch wait fix** | ✅ Merged | `run_experiment.py` + `tests/test_batch_manager.py` |

### What failed or partial

| Campaign | Status | Notes |
|----------|--------|-------|
| **Overnight resume (Spot medium batch03+)** | ❌ Stopped 2026-07-11 | DNS failure to `oauth2.googleapis.com` / AWS |
| **Micro-grid low-N (4 configs)** | ⚠️ Partial | Only 3 OD low reps @ D=5k N=1 before network fail |
| **Overnight Phase B OD high-N** | ⏸ Not started | N=150,185 validation |

### Single most important conclusion

> **Wall clock / cluster_parallel** shows a **U-curve** with optimum at **N=5–16** for D=10k–50k (Spot, warm CE). The paper’s analytical **N*(D)≈107–170** was fit on **N≥25 only** and **full end-to-end** times — it does **not** transfer to our low-N probes without refitting.

---

## Part 2 — Experiment catalog

### 2.1 Infrastructure fix (prerequisite for N=1 micro-grid)

**Issue:** `submit_batch_job()` omits `arrayProperties` when `n_nodes==1`, but `_wait_for_array_job_cluster()` only polled array children → false 7200 s timeouts.

**Fix:** `_wait_for_single_batch_job()` in `experiments/run_experiment.py`; array waiter delegates when `expected_size <= 1`.

**Test:** `tests/test_batch_manager.py`

---

### 2.2 Probe: D=10k low-N Spot

| Field | Value |
|-------|-------|
| **Experiment ID** | `probe_d10k_low_n_spot` |
| **Config** | `experiments/configs/probe_d10k_low_n_spot.yaml` |
| **Run date** | 2026-07-13 |
| **Grid** | D=10,000 × N={5,10,15,25} × 3 replicas |
| **Tier** | low SMILES, Spot, compute_only |
| **Results dir** | `experiments/results/probe_d10k_low_n_spot_20260713_214728/` |
| **Log** | `tmp/probe_d10k_low_n.log` |

**Medians (cluster_parallel, s):**

| N | 5 | 10 | 15 | 25 |
|---|---|----|----|-----|
| cp | **17.3** | 47.5 | 40.1 | 72.9 |
| comp | 15.6 | 7.6 | 5.1 | 3.0 |

**Empirical N\*** = **5** (no interior U — monotone increasing for N≥5).

---

### 2.3 Probe: D=50k pow2 — initial 1-rep (Spot + OD)

| Field | Spot | On-Demand |
|-------|------|-----------|
| **Experiment ID** | `probe_d50k_pow2_spot` | `probe_d50k_pow2_ondemand` |
| **Config** | `probe_d50k_pow2_spot.yaml` | `probe_d50k_pow2_ondemand.yaml` |
| **Run date** | 2026-07-13 | 2026-07-14 |
| **Grid** | D=50k × N={2,4,8,16,32} × 1 rep | same (+ N=32 resumed via `probe_d50k_pow2_ondemand_n32.yaml`) |
| **Results** | `experiments/results/probe_d50k_pow2_spot_20260713_222446/` | `experiments/results/probe_d50k_pow2_ondemand_20260714_083435/` |
| **Log** | `tmp/probe_d50k_pow2.log` | (same log) |

**Finding:** First evidence of U-shape on Spot; compute scales 183→12 s as N doubles; scheduling dominates at high N.

---

### 2.4 Probe: D=50k pow2 — full 2-rep sweeps (Spot)

| Field | Spot low | Spot medium |
|-------|----------|-------------|
| **Experiment ID** | `probe_d50k_pow2_spot_low` | `probe_d50k_pow2_spot_medium` |
| **Config** | `probe_d50k_pow2_spot_low.yaml` | `probe_d50k_pow2_spot_medium.yaml` |
| **Run date** | 2026-07-14 ~09:02 | 2026-07-14 ~09:57 |
| **Grid** | D=50k × N={2,4,8,16,32,64,128} × 2 reps | same |
| **Results** | `experiments/results/probe_d50k_pow2_spot_low_20260714_090237/` | `.../probe_d50k_pow2_spot_medium_20260714_095725/` |
| **Log** | `tmp/probe_d50k_pow2_spot_sweep.log` | (same file) |

**Medians cluster_parallel (s):**

| N | 2 | 4 | 8 | 16 | 32 | 64 | 128 |
|---|----|----|-----|-----|-----|-----|------|
| **low** | 186 | 130 | 113 | **106** | 186* | 146 | 166 |
| **medium** | 405 | 242 | **179** | 190 | 190 | 216 | 323 |

\*N=32 low Spot outlier — scheduling spike; confirm with 3rd rep.

**Cost/cell (Spot):** ~$0.0087–0.0216 (empirical Sheets; not estimator).

---

### 2.5 Probe: D=50k pow2 — full 2-rep sweeps (On-Demand)

| Field | OD low | OD medium |
|-------|--------|-----------|
| **Experiment ID** | `probe_d50k_pow2_ondemand_low` | `probe_d50k_pow2_ondemand_medium` |
| **Config** | `probe_d50k_pow2_ondemand_low.yaml` | `probe_d50k_pow2_ondemand_medium.yaml` |
| **Run date** | 2026-07-14 ~13:07 | 2026-07-14 ~14:01 |
| **Grid** | D=50k × N={2,4,8,16,32,64,128} × 2 reps | same |
| **Results** | `experiments/results/probe_d50k_pow2_ondemand_low_20260714_130755/` | `.../probe_d50k_pow2_ondemand_medium_20260714_140126/` |
| **Log** | `tmp/probe_d50k_pow2_ondemand_sweep.log` | (same file) |

**Medians cluster_parallel (s):**

| N | 2 | 4 | 8 | 16 | 32 | 64 | 128 |
|---|----|----|-----|-----|-----|-----|------|
| **low** | 184 | 141 | **101** | 106 | 113 | 145 | 161 |
| **medium** | 383 | 210 | 191 | 201 | **188** | 214 | 295 |

**Spot vs OD:** timing within ~5% at optimum; OD ~**3×** cost ($0.028 vs $0.009 low tier).

---

### 2.6 Overnight full grid (context baseline)

| Field | Value |
|-------|-------|
| **Experiment IDs** | `overnight_spot_data_low`, `overnight_spot_data_medium`, `overnight_od_shape_low`, … |
| **Grid** | D={5k…50k} × N={25,50,75,100,125,(150,185)} × 10 reps (Spot data pass) |
| **Report** | `tmp/overnight_run_report.md` |
| **Resume state** | `tmp/overnight_resume_state.json` (stopped mid Spot medium, ~$2.93 cumulative) |
| **Log** | `tmp/overnight_run.log` |

**Use for:** D-sweep at fixed N=25; comparison in Panel F of analysis figure.  
**N=25 @ D=50k Spot low:** cluster_parallel median **105 s** — accidentally near pow2 optimum (106 s @ N=16).

**Spot failure boundary:** N≥150 → 100% fail rate at D=5k (capacity / shard issues).

---

### 2.7 Micro-grid low-N (incomplete)

| Field | Value |
|-------|-------|
| **Experiment IDs** | `micro_grid_low_n_low_ondemand`, `micro_grid_low_n_low_spot`, `micro_grid_low_n_medium_*` |
| **Configs** | `experiments/configs/micro_grid_low_n_*.yaml` |
| **Grid** | D={5k,10k} × N={1,5,10,15,25} × 5 reps × 4 tier/provisioning combos |
| **Report** | `tmp/micro_grid_low_n_report.md` |
| **Outcome** | Network failure 2026-07-11; only partial OD low data |

**Note:** Partially superseded by probe_d10k and probe_d50k campaigns; micro-grid still valuable for **N=1** baseline once re-run.

---

## Part 3 — Timing metrics (do not mix)

| Metric | Sheets column | Definition | Use for U-curve? |
|--------|---------------|------------|------------------|
| **Computation** | L | Max shard wall time | ❌ Monotonic ↓ in N |
| **Scheduling** | — | max(start) − min(start) among children | Component |
| **Cluster Parallel** | O/V | First child start → last child stop | ✅ Probes |
| **Cluster Init** | — | CE spin-up | Component |
| **Wall Clock** | W | S3 + init + cluster_parallel | ✅ Best paper match |
| **Cost** | — | Empirical USD from Sheets | ✅ Report ~$0.005–0.03/cell |

**Paper PDF tables** (`data/paper_execution_times.json`) = full end-to-end times, N∈{25…185}.

---

## Part 4 — Consolidated findings

### 4.1 Empirical optima (latest probes)

| Dataset | Tier | Provisioning | N_emp | cluster_parallel | Cost/cell |
|---------|------|--------------|-------|------------------|-----------|
| D=10k | low | Spot | **5** | 17 s | ~$0.002 |
| D=50k | low | Spot | **16** | 106 s | ~$0.009 |
| D=50k | low | OD | **8** | 101 s | ~$0.028 |
| D=50k | medium | Spot | **8** | 179 s | ~$0.016 |
| D=50k | medium | OD | **32** | 188 s | ~$0.059 |

### 4.2 Mechanism (decomposition)

- **Computation** ≈ D/N — halves when N doubles (perfect weak scaling).
- **Scheduling stagger** grows with N — dominates at N≥32.
- **U-curve** = trade-off between under-parallelized compute (low N) and orchestration (high N).

### 4.3 Paper model vs data

| Source | N* @ D=50k | Notes |
|--------|------------|-------|
| Paper PDF fit `N*(D)=-(b+eD)/(2d)` | **170** | N grid 25–185 only |
| Paper PDF empirical argmin | **185** (edge) | Shallow U on right |
| Our probe Spot low | **16** | cluster_parallel |
| Our overnight N=25 | 25 (152 s wall) | Suboptimal vs N=16 |

See **`tmp/nstar_math_analysis.md`** for full derivative derivation and refit recommendations.

### 4.4 Known anomalies

1. **Spot low N=32:** cp=186 s vs OD 113 s — likely 2-rep scheduling outlier.
2. **Cost estimator:** ~70–90× too high vs Sheets — use empirical costs in paper.
3. **CE cold start:** was main noise source; mitigated with 20-min scale-down delay.

---

## Part 5 — Artifacts index

### Figures

| File | Description |
|------|-------------|
| `tmp/probe_analysis_panel.png` | 6-panel: Spot/OD, low/med, D=10k vs 50k, overnight N=25 |
| `tmp/probe_analysis_decomposition.png` | Compute vs scheduling stacks @ D=50k |
| `tmp/probe_d50k_pow2_spot_low_medium_viz.png` | Spot low vs medium (2-rep) |
| `tmp/probe_d50k_pow2_viz.png` | Early 1-rep Spot vs OD |
| `tmp/probe_d50k_pow2_spot_od_viz.png` | Full 4-series Spot+OD |

### JSON / tables

| File | Description |
|------|-------------|
| `tmp/probe_analysis_summary.json` | All medians + optima |
| `tmp/probe_d50k_pow2_spot_od_summary.json` | Spot/OD median cp by N |
| `tmp/probe_d50k_pow2_spot_low_medium_summary.json` | Spot-only medians |
| `tmp/handoff_embedded_data.json` | **Consolidated bundle** (all JSON below) |
| `data/paper_fitted_model.json` | PDF Table 1+2 OLS coefficients |
| `data/paper_execution_times.json` | Transcribed paper tables (170 rows) |

**Full inline copies:** see **Part 11** at end of this document.

### Narrative docs

| File | Description |
|------|-------------|
| `tmp/probe_analysis_conclusions.md` | Panel conclusions + paper narrative |
| `tmp/nstar_math_analysis.md` | N*(D) derivative + gap analysis |
| `tmp/overnight_run_report.md` | Overnight grid failures + costs |
| `tmp/micro_grid_low_n_report.md` | Micro-grid abort report |

### Plot scripts (regenerate)

```bash
cd chemoinformatics-descriptor-computation
source .env && export PYTHONPATH=.
python scripts/plot_probe_analysis_panel.py
python scripts/plot_probe_d50k_pow2_spot_od.py
python scripts/plot_probe_d50k_pow2_spot_low_medium.py
```

### Logs

| Log | Experiment |
|-----|------------|
| `tmp/probe_d10k_low_n.log` | D=10k probe |
| `tmp/probe_d50k_pow2.log` | D=50k 1-rep |
| `tmp/probe_d50k_pow2_spot_sweep.log` | Spot 2-rep sweep |
| `tmp/probe_d50k_pow2_ondemand_sweep.log` | OD 2-rep sweep |
| `tmp/overnight_run.log` | Overnight resume |

---

## Part 6 — Paper model quick reference

**Model:**

\[
T(N,D) = a + bN + cD + dN^2 + eND
\]

**FOC (optimal nodes):**

\[
N^*(D) = -\frac{b + eD}{2d} \quad \text{(requires } d > 0\text{)}
\]

**Paper coefficients (R²=0.851):** `a=264.35, b=-4.0446, c=0.01234, d=0.02031, e=-5.716×10⁻⁵`

**Code:**

```bash
python src/core/model.py optimal-table    # N* from paper fit
python src/core/model.py fit-paper        # refit from PDF tables
python src/core/model.py predict 16 50000 # T(N,D) prediction
```

**Our overnight wall_clock OLS:** fitted **d &lt; 0** → paper formula not applicable without refit on expanded N grid.

---

## Part 7 — Open work for next analyst

### High priority

- [ ] **3rd replica** at D=50k N=32 Spot low — settle scheduling outlier
- [ ] **Refit T(N,D)** on `wall_clock` merging overnight + probes (include N=2…128)
- [ ] **Table:** analytical N* vs empirical argmin vs paper N* — all D
- [ ] **Cost frontier figure:** time × $/cell for Spot vs OD

### Medium priority

- [ ] **D=100k pow2 sweep** (N=8–64) — expect optimum shifts right
- [ ] **Re-run micro-grid** N=1 baseline (fix is merged)
- [ ] **Resume overnight** Spot medium + Phase B OD high-N when network stable
- [ ] **Medium D=10k probe** — only low tier probed at 10k

### Paper writing

- [ ] Update recommendation table: D=10k→N=5, D=50k low→N=16 Spot
- [ ] Document metric choice (wall_clock vs cluster_parallel) explicitly
- [ ] Explain why paper N*≈170 vs empirical N*≈16 (N grid + orchestration regime)
- [ ] Replace estimator costs with empirical Sheets costs

---

## Part 8 — Reproduce & extend

### Environment

```bash
conda activate venv_chemoinformatics
cd chemoinformatics-descriptor-computation
source .env
export PYTHONPATH=.
export SKIP_PRE_RUN_ESTIMATE=1
export BATCH_RUNNING_DEADLINE_SEC=900
```

### Run a probe config

```bash
python experiments/run_experiment.py \
  --config experiments/configs/probe_d50k_pow2_spot_low.yaml
```

### Pull medians from Sheets (Python)

```python
import os
from src.monitoring.sheets import read_results_rows
rows = read_results_rows(os.environ["GOOGLE_SHEETS_ID"])
# Filter: Experiment ID == "probe_d50k_pow2_spot_low", Status == SUCCEEDED
```

### Pull data for plotting

All plot scripts read live from Google Sheets via `GOOGLE_SHEETS_ID` in `.env`.

---

## Part 9 — Experiment ID master list (latest session)

| Experiment ID | Status | Purpose |
|---------------|--------|---------|
| `probe_d10k_low_n_spot` | ✅ | D=10k N=5–25 |
| `probe_d50k_pow2_spot` | ✅ | D=50k 1-rep Spot N≤32 |
| `probe_d50k_pow2_ondemand` | ✅ | D=50k 1-rep OD N≤32 |
| `probe_d50k_pow2_spot_low` | ✅ | D=50k 2-rep Spot low |
| `probe_d50k_pow2_spot_medium` | ✅ | D=50k 2-rep Spot medium |
| `probe_d50k_pow2_ondemand_low` | ✅ | D=50k 2-rep OD low |
| `probe_d50k_pow2_ondemand_medium` | ✅ | D=50k 2-rep OD medium |
| `overnight_spot_data_low` | ✅ (partial resume) | D=5k–50k N=25–125 baseline |
| `overnight_spot_data_medium` | ⚠️ partial | Stopped batch03 |
| `micro_grid_low_n_low_ondemand` | ⚠️ 3 cells | N=1 OD low only |
| `probe_d20k_d40k_pow2_spot_low` | ✅ 2026-07-14 | D=20k/40k N=2–32 low 1-rep |
| `probe_d20k_d40k_pow2_spot_medium` | ✅ 2026-07-14 | D=20k/40k N=2–32 medium 1-rep |
| `probe_d20k_d40k_pow2_spot_low_ext` | ✅ 2026-07-14 | D=20k/40k N=64,128 low 1-rep |
| `probe_d20k_d40k_pow2_spot_medium_ext` | ✅ 2026-07-14 | D=20k/40k N=64,128 medium 1-rep |
| `confirm_d50k_n32_spot_low` | ✅ 5-rep done | D=50k N=32: med cp=127s (was 186); still sched-dominated, 1/5 outlier |
| `confirm_d20k_n8_spot_medium` | ✅ 5-rep done | D=20k N=8: med cp=81s (was 157); 1/5 spike — original was outlier |
| `rep3_d5k_pow2_spot_low` | 🔄 parallel | D=5k N=2…128 Spot low ×3 |
| `rep3_d5k_pow2_spot_medium` | 🔄 parallel | D=5k N=2…128 Spot medium ×3 |
| `rep3_d10k_pow2_spot_medium` | 🔄 parallel | D=10k N=2…128 Spot medium ×3 |
| `rep3_d20k_pow2_spot_low` | 🔄 parallel | D=20k N=2…128 Spot low ×3 |
| `rep3_d20k_pow2_spot_medium` | 🔄 parallel | D=20k N=2…128 Spot medium ×3 |
| `rep3_d40k_pow2_spot_low` | 🔄 parallel | D=40k N=2…128 Spot low ×3 |
| `rep3_d40k_pow2_spot_medium` | 🔄 parallel | D=40k N=2…128 Spot medium ×3 |

**Parallel campaign (2026-07-16):** 7 configs × 7 N × 3 reps = **147** Batch array parents. Launcher: `scripts/run_rep3_pow2_parallel.sh`. Logs: `tmp/rep3_pow2_parallel/*.log`.

> **Correction (2026-07-16):** Do **not** claim a flat empirical N*=16 plateau from discrete pow2 argmins — that is a sampling artifact. Prefer fitted `T(N,D)` / per-D quadratic vertices (N* grows with D, smaller magnitude than paper). Lead with Panel I (scheduling fraction). See `tmp/probe_analysis_conclusions.md`.

---

## Part 10 — Recommended paper claims (evidence-backed)

1. Descriptor **compute scales ~1/N**; **end-to-end time** is bounded by Batch **scheduling stagger**.
2. **U-curve** exists in cluster_parallel / wall_clock; minimum at **N=5 (D=10k)** and **N=8–16 (D=50k)** for Spot low tier.
3. **Spot ≈ OD** latency when CE warm; Spot **~3× cheaper**.
4. Paper’s **N*(D)** formula is mathematically correct but coefficients trained on **N≥25** — practical optimum is **much lower** with modern Batch + pow2 sweeps.
5. Fixed **N=25** (overnight grid) is near-optimal only at **D=50k**; suboptimal by up to **~47%** at D=10k.

---


---

## Part 11 — Embedded JSON data (all results)

Self-contained data appendix for offline analysis. Machine-readable bundle: `tmp/handoff_embedded_data.json`.
All values are **medians** from Google Sheets (`Status=SUCCEEDED`) unless noted as paper PDF transcription.

### 11.1 — `probe_analysis_summary.json` (optima + full series)

```json
{
  "optima": {
    "spot_low_d50k": {
      "N": 16,
      "cluster_parallel": 105.7775,
      "computation": 23.332
    },
    "spot_med_d50k": {
      "N": 8,
      "cluster_parallel": 178.685,
      "computation": 92.1155
    },
    "od_low_d50k": {
      "N": 8,
      "cluster_parallel": 101.325,
      "computation": 47.297
    },
    "od_med_d50k": {
      "N": 32,
      "cluster_parallel": 187.998,
      "computation": 24.563499999999998
    },
    "spot_d10k": {
      "N": 5,
      "cluster_parallel": 17.325,
      "computation": 15.589
    }
  },
  "overnight_n25_d50k_cp": 105.1055,
  "series": {
    "spot_low": {
      "2": {
        "cp": 185.5195,
        "comp": 184.1875,
        "sched": 0.006,
        "init": 110.028,
        "cost": 0.00865,
        "n": 2
      },
      "4": {
        "cp": 129.598,
        "comp": 92.747,
        "sched": 36.4345,
        "init": 69.68599999999999,
        "cost": 0.0087,
        "n": 2
      },
      "8": {
        "cp": 112.7875,
        "comp": 46.7285,
        "sched": 65.812,
        "init": 64.3365,
        "cost": 0.0088,
        "n": 2
      },
      "16": {
        "cp": 105.7775,
        "comp": 23.332,
        "sched": 82.19800000000001,
        "init": 42.1235,
        "cost": 0.009,
        "n": 2
      },
      "32": {
        "cp": 185.92000000000002,
        "comp": 11.671,
        "sched": 173.361,
        "init": 32.959500000000006,
        "cost": 0.00935,
        "n": 2
      },
      "64": {
        "cp": 145.54149999999998,
        "comp": 5.978,
        "sched": 138.65,
        "init": 47.558,
        "cost": 0.0104,
        "n": 2
      },
      "128": {
        "cp": 165.824,
        "comp": 2.966,
        "sched": 161.868,
        "init": 34.584,
        "cost": 0.012199999999999999,
        "n": 2
      }
    },
    "spot_med": {
      "2": {
        "cp": 405.153,
        "comp": 372.2025,
        "sched": 18.4325,
        "init": 12.004,
        "cost": 0.0086,
        "n": 1
      },
      "4": {
        "cp": 242.426,
        "comp": 183.34,
        "sched": 62.9455,
        "init": 47.9035,
        "cost": 0.01645,
        "n": 2
      },
      "8": {
        "cp": 178.685,
        "comp": 92.1155,
        "sched": 90.4545,
        "init": 57.6925,
        "cost": 0.01645,
        "n": 2
      },
      "16": {
        "cp": 189.90449999999998,
        "comp": 46.994,
        "sched": 144.824,
        "init": 47.417,
        "cost": 0.017099999999999997,
        "n": 2
      },
      "32": {
        "cp": 189.7275,
        "comp": 24.0165,
        "sched": 165.00900000000001,
        "init": 65.292,
        "cost": 0.01785,
        "n": 2
      },
      "64": {
        "cp": 215.5075,
        "comp": 12.746500000000001,
        "sched": 202.1275,
        "init": 51.789,
        "cost": 0.0195,
        "n": 2
      },
      "128": {
        "cp": 322.75350000000003,
        "comp": 6.4695,
        "sched": 315.6635,
        "init": 26.912,
        "cost": 0.0216,
        "n": 2
      }
    },
    "od_low": {
      "2": {
        "cp": 183.9325,
        "comp": 182.586,
        "sched": 0.002,
        "init": 136.9615,
        "cost": 0.027450000000000002,
        "n": 2
      },
      "4": {
        "cp": 141.3465,
        "comp": 95.29849999999999,
        "sched": 44.9475,
        "init": 69.3325,
        "cost": 0.02805,
        "n": 2
      },
      "8": {
        "cp": 101.325,
        "comp": 47.297,
        "sched": 53.3335,
        "init": 35.472,
        "cost": 0.02795,
        "n": 2
      },
      "16": {
        "cp": 106.353,
        "comp": 24.180500000000002,
        "sched": 81.16,
        "init": 38.857,
        "cost": 0.0291,
        "n": 2
      },
      "32": {
        "cp": 113.2655,
        "comp": 12.276,
        "sched": 100.3605,
        "init": 58.417500000000004,
        "cost": 0.0303,
        "n": 2
      },
      "64": {
        "cp": 145.21949999999998,
        "comp": 6.0825,
        "sched": 138.198,
        "init": 29.388,
        "cost": 0.033,
        "n": 2
      },
      "128": {
        "cp": 161.1935,
        "comp": 3.0765,
        "sched": 157.2505,
        "init": 70.5095,
        "cost": 0.0392,
        "n": 2
      }
    },
    "od_med": {
      "2": {
        "cp": 383.276,
        "comp": 381.70799999999997,
        "sched": 0.4585,
        "init": 59.494,
        "cost": 0.05665,
        "n": 2
      },
      "4": {
        "cp": 210.308,
        "comp": 189.6775,
        "sched": 22.7595,
        "init": 95.0505,
        "cost": 0.05575,
        "n": 2
      },
      "8": {
        "cp": 191.1585,
        "comp": 99.039,
        "sched": 96.3475,
        "init": 48.9095,
        "cost": 0.0566,
        "n": 2
      },
      "16": {
        "cp": 200.507,
        "comp": 48.36,
        "sched": 153.02,
        "init": 62.876999999999995,
        "cost": 0.0571,
        "n": 2
      },
      "32": {
        "cp": 187.998,
        "comp": 24.563499999999998,
        "sched": 163.18849999999998,
        "init": 36.538,
        "cost": 0.059,
        "n": 2
      },
      "64": {
        "cp": 214.401,
        "comp": 12.5515,
        "sched": 201.4015,
        "init": 61.59,
        "cost": 0.06185,
        "n": 2
      },
      "128": {
        "cp": 294.58349999999996,
        "comp": 6.324,
        "sched": 287.58050000000003,
        "init": 28.757,
        "cost": 0.0678,
        "n": 2
      }
    },
    "d10k": {
      "5": {
        "cp": 17.325,
        "comp": 15.589,
        "sched": 1.146,
        "init": 76.898,
        "cost": 0.0018,
        "n": 3
      },
      "10": {
        "cp": 47.534,
        "comp": 7.629,
        "sched": 39.166,
        "init": 70.931,
        "cost": 0.002,
        "n": 3
      },
      "15": {
        "cp": 40.123,
        "comp": 5.093,
        "sched": 34.029,
        "init": 36.127,
        "cost": 0.0021,
        "n": 3
      },
      "25": {
        "cp": 72.895,
        "comp": 2.959,
        "sched": 68.81,
        "init": 46.17,
        "cost": 0.0023,
        "n": 3
      }
    }
  }
}
```

### 11.2 — `probe_d50k_pow2_spot_od_summary.json` (cluster_parallel medians)

```json
{
  "Spot low": {
    "2": 185.5195,
    "4": 129.598,
    "8": 112.7875,
    "16": 105.7775,
    "32": 185.92000000000002,
    "64": 145.54149999999998,
    "128": 165.824
  },
  "Spot medium": {
    "2": 405.153,
    "4": 242.426,
    "8": 178.685,
    "16": 189.90449999999998,
    "32": 189.7275,
    "64": 215.5075,
    "128": 322.75350000000003
  },
  "OD low": {
    "2": 183.9325,
    "4": 141.3465,
    "8": 101.325,
    "16": 106.353,
    "32": 113.2655,
    "64": 145.21949999999998,
    "128": 161.1935
  },
  "OD medium": {
    "2": 383.276,
    "4": 210.308,
    "8": 191.1585,
    "16": 200.507,
    "32": 187.998,
    "64": 214.401,
    "128": 294.58349999999996
  },
  "OD low (legacy 1-rep)": {
    "2": 183.669,
    "4": 210.361,
    "8": 96.374,
    "16": 105.472,
    "32": 51.663
  }
}
```

### 11.3 — `probe_d50k_pow2_spot_low_medium_summary.json`

```json
{
  "low": {
    "2": 185.5195,
    "4": 129.598,
    "8": 112.7875,
    "16": 105.7775,
    "32": 185.92000000000002,
    "64": 145.54149999999998,
    "128": 165.824
  },
  "medium": {
    "2": 405.153,
    "4": 242.426,
    "8": 178.685,
    "16": 189.90449999999998,
    "32": 189.7275,
    "64": 215.5075,
    "128": 322.75350000000003
  }
}
```

### 11.4 — `data/paper_fitted_model.json` (PDF Table 1+2 OLS)

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

### 11.5 — Paper analytical N*(D) table

```json
{
  "5000": {
    "N_star": 107,
    "T_pred_sec": 95.3
  },
  "10000": {
    "N_star": 114,
    "T_pred_sec": 125.5
  },
  "15000": {
    "N_star": 121,
    "T_pred_sec": 153.7
  },
  "20000": {
    "N_star": 128,
    "T_pred_sec": 180.0
  },
  "25000": {
    "N_star": 135,
    "T_pred_sec": 204.2
  },
  "30000": {
    "N_star": 142,
    "T_pred_sec": 226.4
  },
  "35000": {
    "N_star": 149,
    "T_pred_sec": 246.6
  },
  "40000": {
    "N_star": 156,
    "T_pred_sec": 264.7
  },
  "45000": {
    "N_star": 163,
    "T_pred_sec": 280.9
  },
  "50000": {
    "N_star": 170,
    "T_pred_sec": 295.1
  }
}
```

### 11.6 — Paper PDF empirical argmin metadata

```json
{
  "provenance": "paper_pdf_table_transcription",
  "n_rows": 170,
  "node_configs": [
    25,
    35,
    45,
    55,
    65,
    75,
    85,
    95,
    105,
    115,
    125,
    135,
    145,
    155,
    165,
    175,
    185
  ],
  "dataset_sizes": [
    5000,
    10000,
    15000,
    20000,
    25000,
    30000,
    35000,
    40000,
    45000,
    50000
  ],
  "empirical_argmin_by_D": {
    "5000": {
      "N": 75,
      "execution_time_sec": 130.62
    },
    "10000": {
      "N": 145,
      "execution_time_sec": 152.2
    },
    "15000": {
      "N": 105,
      "execution_time_sec": 176.36
    },
    "20000": {
      "N": 145,
      "execution_time_sec": 183.19
    },
    "25000": {
      "N": 185,
      "execution_time_sec": 212.91
    },
    "30000": {
      "N": 175,
      "execution_time_sec": 242.88
    },
    "35000": {
      "N": 165,
      "execution_time_sec": 239.73
    },
    "40000": {
      "N": 145,
      "execution_time_sec": 251.3
    },
    "45000": {
      "N": 145,
      "execution_time_sec": 297.45
    },
    "50000": {
      "N": 185,
      "execution_time_sec": 307.57
    }
  }
}
```

### 11.7 — Overnight resume / run state

```json
{
  "overnight_resume_state": {
    "started_at": "2026-07-10T11:24:43Z",
    "step": "A_spot",
    "jobs_submitted": 370,
    "cumulative_cost_usd": 2.9292,
    "active_experiment_ids": [
      "overnight_spot_data_low",
      "overnight_spot_data_medium"
    ]
  },
  "overnight_run_state": {
    "started_at": "2026-07-10T00:29:35Z",
    "step": "3_spot_data",
    "jobs_submitted": 184,
    "cumulative_cost_usd": 0.2946,
    "active_experiment_ids": [
      "overnight_spot_data_low",
      "overnight_spot_data_medium"
    ]
  }
}
```

### 11.8 — Google Sheets medians by experiment ID

```json
{
  "probe_d10k_low_n_spot": {
    "D10000_N10": {
      "cluster_parallel_sec": 47.534,
      "computation_sec": 7.629,
      "scheduling_sec": 39.166,
      "cluster_init_sec": 70.931,
      "wall_clock_sec": 111.215,
      "cost_usd": 0.002,
      "n_reps": 3
    },
    "D10000_N15": {
      "cluster_parallel_sec": 40.123,
      "computation_sec": 5.093,
      "scheduling_sec": 34.029,
      "cluster_init_sec": 36.127,
      "wall_clock_sec": 81.257,
      "cost_usd": 0.0021,
      "n_reps": 3
    },
    "D10000_N25": {
      "cluster_parallel_sec": 72.895,
      "computation_sec": 2.959,
      "scheduling_sec": 68.81,
      "cluster_init_sec": 46.17,
      "wall_clock_sec": 138.719,
      "cost_usd": 0.0023,
      "n_reps": 3
    },
    "D10000_N5": {
      "cluster_parallel_sec": 17.325,
      "computation_sec": 15.589,
      "scheduling_sec": 1.146,
      "cluster_init_sec": 76.898,
      "wall_clock_sec": 95.364,
      "cost_usd": 0.0018,
      "n_reps": 3
    }
  },
  "probe_d50k_pow2_spot": {
    "D50000_N2": {
      "cluster_parallel_sec": 222.071,
      "computation_sec": 182.814,
      "scheduling_sec": 38.029,
      "cluster_init_sec": 53.002,
      "wall_clock_sec": 277.331,
      "cost_usd": 0.0085,
      "n_reps": 1
    },
    "D50000_N32": {
      "cluster_parallel_sec": 133.043,
      "computation_sec": 12.098,
      "scheduling_sec": 120.771,
      "cluster_init_sec": 37.796,
      "wall_clock_sec": 179.067,
      "cost_usd": 0.0094,
      "n_reps": 1
    },
    "D50000_N4": {
      "cluster_parallel_sec": 131.19,
      "computation_sec": 93.679,
      "scheduling_sec": 36.419,
      "cluster_init_sec": 59.619,
      "wall_clock_sec": 196.427,
      "cost_usd": 0.0087,
      "n_reps": 1
    },
    "D50000_N8": {
      "cluster_parallel_sec": 101.485,
      "computation_sec": 46.869,
      "scheduling_sec": 54.325,
      "cluster_init_sec": 67.128,
      "wall_clock_sec": 173.781,
      "cost_usd": 0.0087,
      "n_reps": 1
    }
  },
  "probe_d50k_pow2_ondemand": {
    "D50000_N16": {
      "cluster_parallel_sec": 105.472,
      "computation_sec": 23.05,
      "scheduling_sec": 81.452,
      "cluster_init_sec": 44.133,
      "wall_clock_sec": 159.315,
      "cost_usd": 0.0287,
      "n_reps": 1
    },
    "D50000_N2": {
      "cluster_parallel_sec": 183.669,
      "computation_sec": 182.545,
      "scheduling_sec": 0.005,
      "cluster_init_sec": 217.329,
      "wall_clock_sec": 406.932,
      "cost_usd": 0.0274,
      "n_reps": 1
    },
    "D50000_N32": {
      "cluster_parallel_sec": 51.663,
      "computation_sec": 11.753,
      "scheduling_sec": 38.9,
      "cluster_init_sec": 201.255,
      "wall_clock_sec": 256.494,
      "cost_usd": 0.0306,
      "n_reps": 1
    },
    "D50000_N4": {
      "cluster_parallel_sec": 210.361,
      "computation_sec": 91.77,
      "scheduling_sec": 118.537,
      "cluster_init_sec": 20.359,
      "wall_clock_sec": 232.892,
      "cost_usd": 0.0276,
      "n_reps": 1
    },
    "D50000_N8": {
      "cluster_parallel_sec": 96.374,
      "computation_sec": 46.006,
      "scheduling_sec": 49.115,
      "cluster_init_sec": 32.946,
      "wall_clock_sec": 137.537,
      "cost_usd": 0.0279,
      "n_reps": 1
    }
  },
  "probe_d50k_pow2_spot_low": {
    "D50000_N128": {
      "cluster_parallel_sec": 165.824,
      "computation_sec": 2.966,
      "scheduling_sec": 161.868,
      "cluster_init_sec": 34.584,
      "wall_clock_sec": 213.949,
      "cost_usd": 0.0122,
      "n_reps": 2
    },
    "D50000_N16": {
      "cluster_parallel_sec": 105.7775,
      "computation_sec": 23.332,
      "scheduling_sec": 82.198,
      "cluster_init_sec": 42.1235,
      "wall_clock_sec": 150.4255,
      "cost_usd": 0.009,
      "n_reps": 2
    },
    "D50000_N2": {
      "cluster_parallel_sec": 185.5195,
      "computation_sec": 184.1875,
      "scheduling_sec": 0.006,
      "cluster_init_sec": 110.028,
      "wall_clock_sec": 296.2405,
      "cost_usd": 0.0086,
      "n_reps": 2
    },
    "D50000_N32": {
      "cluster_parallel_sec": 185.92,
      "computation_sec": 11.671,
      "scheduling_sec": 173.361,
      "cluster_init_sec": 32.9595,
      "wall_clock_sec": 222.495,
      "cost_usd": 0.0094,
      "n_reps": 2
    },
    "D50000_N4": {
      "cluster_parallel_sec": 129.598,
      "computation_sec": 92.747,
      "scheduling_sec": 36.4345,
      "cluster_init_sec": 69.686,
      "wall_clock_sec": 200.2465,
      "cost_usd": 0.0087,
      "n_reps": 2
    },
    "D50000_N64": {
      "cluster_parallel_sec": 145.5415,
      "computation_sec": 5.978,
      "scheduling_sec": 138.65,
      "cluster_init_sec": 47.558,
      "wall_clock_sec": 200.001,
      "cost_usd": 0.0104,
      "n_reps": 2
    },
    "D50000_N8": {
      "cluster_parallel_sec": 112.7875,
      "computation_sec": 46.7285,
      "scheduling_sec": 65.812,
      "cluster_init_sec": 64.3365,
      "wall_clock_sec": 178.4335,
      "cost_usd": 0.0088,
      "n_reps": 2
    }
  },
  "probe_d50k_pow2_spot_medium": {
    "D50000_N128": {
      "cluster_parallel_sec": 322.7535,
      "computation_sec": 6.4695,
      "scheduling_sec": 315.6635,
      "cluster_init_sec": 26.912,
      "wall_clock_sec": 365.246,
      "cost_usd": 0.0216,
      "n_reps": 2
    },
    "D50000_N16": {
      "cluster_parallel_sec": 189.9045,
      "computation_sec": 46.994,
      "scheduling_sec": 144.824,
      "cluster_init_sec": 47.417,
      "wall_clock_sec": 241.663,
      "cost_usd": 0.0171,
      "n_reps": 2
    },
    "D50000_N2": {
      "cluster_parallel_sec": 405.153,
      "computation_sec": 369.614,
      "scheduling_sec": 36.865,
      "cluster_init_sec": 24.008,
      "wall_clock_sec": 432.135,
      "cost_usd": 0.0172,
      "n_reps": 1
    },
    "D50000_N32": {
      "cluster_parallel_sec": 189.7275,
      "computation_sec": 24.0165,
      "scheduling_sec": 165.009,
      "cluster_init_sec": 65.292,
      "wall_clock_sec": 259.581,
      "cost_usd": 0.0179,
      "n_reps": 2
    },
    "D50000_N4": {
      "cluster_parallel_sec": 242.426,
      "computation_sec": 183.34,
      "scheduling_sec": 62.9455,
      "cluster_init_sec": 47.9035,
      "wall_clock_sec": 291.6905,
      "cost_usd": 0.0164,
      "n_reps": 2
    },
    "D50000_N64": {
      "cluster_parallel_sec": 215.5075,
      "computation_sec": 12.7465,
      "scheduling_sec": 202.1275,
      "cluster_init_sec": 51.789,
      "wall_clock_sec": 274.832,
      "cost_usd": 0.0195,
      "n_reps": 2
    },
    "D50000_N8": {
      "cluster_parallel_sec": 178.685,
      "computation_sec": 92.1155,
      "scheduling_sec": 90.4545,
      "cluster_init_sec": 57.6925,
      "wall_clock_sec": 238.01,
      "cost_usd": 0.0164,
      "n_reps": 2
    }
  },
  "probe_d50k_pow2_ondemand_low": {
    "D50000_N128": {
      "cluster_parallel_sec": 161.1935,
      "computation_sec": 3.0765,
      "scheduling_sec": 157.2505,
      "cluster_init_sec": 70.5095,
      "wall_clock_sec": 245.0295,
      "cost_usd": 0.0392,
      "n_reps": 2
    },
    "D50000_N16": {
      "cluster_parallel_sec": 106.353,
      "computation_sec": 24.1805,
      "scheduling_sec": 81.16,
      "cluster_init_sec": 38.857,
      "wall_clock_sec": 147.5295,
      "cost_usd": 0.0291,
      "n_reps": 2
    },
    "D50000_N2": {
      "cluster_parallel_sec": 183.9325,
      "computation_sec": 182.586,
      "scheduling_sec": 0.002,
      "cluster_init_sec": 136.9615,
      "wall_clock_sec": 321.905,
      "cost_usd": 0.0275,
      "n_reps": 2
    },
    "D50000_N32": {
      "cluster_parallel_sec": 113.2655,
      "computation_sec": 12.276,
      "scheduling_sec": 100.3605,
      "cluster_init_sec": 58.4175,
      "wall_clock_sec": 175.4475,
      "cost_usd": 0.0303,
      "n_reps": 2
    },
    "D50000_N4": {
      "cluster_parallel_sec": 141.3465,
      "computation_sec": 95.2985,
      "scheduling_sec": 44.9475,
      "cluster_init_sec": 69.3325,
      "wall_clock_sec": 213.5725,
      "cost_usd": 0.028,
      "n_reps": 2
    },
    "D50000_N64": {
      "cluster_parallel_sec": 145.2195,
      "computation_sec": 6.0825,
      "scheduling_sec": 138.198,
      "cluster_init_sec": 29.388,
      "wall_clock_sec": 180.959,
      "cost_usd": 0.033,
      "n_reps": 2
    },
    "D50000_N8": {
      "cluster_parallel_sec": 101.325,
      "computation_sec": 47.297,
      "scheduling_sec": 53.3335,
      "cluster_init_sec": 35.472,
      "wall_clock_sec": 138.098,
      "cost_usd": 0.0279,
      "n_reps": 2
    }
  },
  "probe_d50k_pow2_ondemand_medium": {
    "D50000_N128": {
      "cluster_parallel_sec": 294.5835,
      "computation_sec": 6.324,
      "scheduling_sec": 287.5805,
      "cluster_init_sec": 28.757,
      "wall_clock_sec": 336.7875,
      "cost_usd": 0.0678,
      "n_reps": 2
    },
    "D50000_N16": {
      "cluster_parallel_sec": 200.507,
      "computation_sec": 48.36,
      "scheduling_sec": 153.02,
      "cluster_init_sec": 62.877,
      "wall_clock_sec": 265.505,
      "cost_usd": 0.0571,
      "n_reps": 2
    },
    "D50000_N2": {
      "cluster_parallel_sec": 383.276,
      "computation_sec": 381.708,
      "scheduling_sec": 0.4585,
      "cluster_init_sec": 59.494,
      "wall_clock_sec": 443.57,
      "cost_usd": 0.0566,
      "n_reps": 2
    },
    "D50000_N32": {
      "cluster_parallel_sec": 187.998,
      "computation_sec": 24.5635,
      "scheduling_sec": 163.1885,
      "cluster_init_sec": 36.538,
      "wall_clock_sec": 229.0575,
      "cost_usd": 0.059,
      "n_reps": 2
    },
    "D50000_N4": {
      "cluster_parallel_sec": 210.308,
      "computation_sec": 189.6775,
      "scheduling_sec": 22.7595,
      "cluster_init_sec": 95.0505,
      "wall_clock_sec": 306.8125,
      "cost_usd": 0.0558,
      "n_reps": 2
    },
    "D50000_N64": {
      "cluster_parallel_sec": 214.401,
      "computation_sec": 12.5515,
      "scheduling_sec": 201.4015,
      "cluster_init_sec": 61.59,
      "wall_clock_sec": 283.139,
      "cost_usd": 0.0619,
      "n_reps": 2
    },
    "D50000_N8": {
      "cluster_parallel_sec": 191.1585,
      "computation_sec": 99.039,
      "scheduling_sec": 96.3475,
      "cluster_init_sec": 48.9095,
      "wall_clock_sec": 242.358,
      "cost_usd": 0.0566,
      "n_reps": 2
    }
  },
  "overnight_spot_data_low": {
    "D10000_N100": {
      "cluster_parallel_sec": 104.49,
      "computation_sec": 0.787,
      "scheduling_sec": 102.485,
      "cluster_init_sec": 49.1715,
      "wall_clock_sec": 185.4425,
      "cost_usd": 0.0049,
      "n_reps": 10
    },
    "D10000_N125": {
      "cluster_parallel_sec": 130.0025,
      "computation_sec": 0.669,
      "scheduling_sec": 128.152,
      "cluster_init_sec": 47.485,
      "wall_clock_sec": 189.48,
      "cost_usd": 0.0058,
      "n_reps": 10
    },
    "D10000_N25": {
      "cluster_parallel_sec": 31.5155,
      "computation_sec": 2.9885,
      "scheduling_sec": 27.3925,
      "cluster_init_sec": 51.846,
      "wall_clock_sec": 85.92,
      "cost_usd": 0.0024,
      "n_reps": 10
    },
    "D10000_N50": {
      "cluster_parallel_sec": 60.4005,
      "computation_sec": 1.511,
      "scheduling_sec": 57.518,
      "cluster_init_sec": 52.2635,
      "wall_clock_sec": 117.9685,
      "cost_usd": 0.0032,
      "n_reps": 10
    },
    "D10000_N75": {
      "cluster_parallel_sec": 90.908,
      "computation_sec": 1.015,
      "scheduling_sec": 88.907,
      "cluster_init_sec": 44.17,
      "wall_clock_sec": 147.4285,
      "cost_usd": 0.0038,
      "n_reps": 10
    },
    "D20000_N100": {
      "cluster_parallel_sec": 122.9845,
      "computation_sec": 1.554,
      "scheduling_sec": 120.0795,
      "cluster_init_sec": 44.0245,
      "wall_clock_sec": 176.976,
      "cost_usd": 0.0064,
      "n_reps": 10
    },
    "D20000_N125": {
      "cluster_parallel_sec": 153.993,
      "computation_sec": 1.2405,
      "scheduling_sec": 151.4915,
      "cluster_init_sec": 41.3735,
      "wall_clock_sec": 214.459,
      "cost_usd": 0.0071,
      "n_reps": 10
    },
    "D20000_N25": {
      "cluster_parallel_sec": 74.839,
      "computation_sec": 5.9215,
      "scheduling_sec": 68.192,
      "cluster_init_sec": 46.317,
      "wall_clock_sec": 126.994,
      "cost_usd": 0.0041,
      "n_reps": 10
    },
    "D20000_N50": {
      "cluster_parallel_sec": 66.3135,
      "computation_sec": 3.078,
      "scheduling_sec": 62.2475,
      "cluster_init_sec": 47.5205,
      "wall_clock_sec": 118.8955,
      "cost_usd": 0.0048,
      "n_reps": 10
    },
    "D20000_N75": {
      "cluster_parallel_sec": 92.5535,
      "computation_sec": 2.085,
      "scheduling_sec": 89.2445,
      "cluster_init_sec": 46.5135,
      "wall_clock_sec": 150.826,
      "cost_usd": 0.0058,
      "n_reps": 10
    },
    "D30000_N100": {
      "cluster_parallel_sec": 123.122,
      "computation_sec": 2.2555,
      "scheduling_sec": 119.837,
      "cluster_init_sec": 36.3245,
      "wall_clock_sec": 173.2455,
      "cost_usd": 0.008,
      "n_reps": 10
    },
    "D30000_N125": {
      "cluster_parallel_sec": 154.3045,
      "computation_sec": 1.8305,
      "scheduling_sec": 151.3205,
      "cluster_init_sec": 41.496,
      "wall_clock_sec": 211.332,
      "cost_usd": 0.0088,
      "n_reps": 10
    },
    "D30000_N25": {
      "cluster_parallel_sec": 68.554,
      "computation_sec": 8.973,
      "scheduling_sec": 58.504,
      "cluster_init_sec": 45.193,
      "wall_clock_sec": 115.9795,
      "cost_usd": 0.0058,
      "n_reps": 10
    },
    "D30000_N50": {
      "cluster_parallel_sec": 110.922,
      "computation_sec": 4.573,
      "scheduling_sec": 105.297,
      "cluster_init_sec": 47.766,
      "wall_clock_sec": 162.8095,
      "cost_usd": 0.0066,
      "n_reps": 10
    },
    "D30000_N75": {
      "cluster_parallel_sec": 103.744,
      "computation_sec": 3.045,
      "scheduling_sec": 99.5715,
      "cluster_init_sec": 44.533,
      "wall_clock_sec": 155.6335,
      "cost_usd": 0.0073,
      "n_reps": 10
    },
    "D40000_N100": {
      "cluster_parallel_sec": 134.8955,
      "computation_sec": 2.9825,
      "scheduling_sec": 130.669,
      "cluster_init_sec": 47.507,
      "wall_clock_sec": 192.127,
      "cost_usd": 0.0097,
      "n_reps": 10
    },
    "D40000_N125": {
      "cluster_parallel_sec": 154.896,
      "computation_sec": 2.4145,
      "scheduling_sec": 151.386,
      "cluster_init_sec": 50.289,
      "wall_clock_sec": 217.403,
      "cost_usd": 0.0104,
      "n_reps": 10
    },
    "D40000_N25": {
      "cluster_parallel_sec": 80.9075,
      "computation_sec": 11.8355,
      "scheduling_sec": 68.0925,
      "cluster_init_sec": 45.3895,
      "wall_clock_sec": 128.8085,
      "cost_usd": 0.0075,
      "n_reps": 10
    },
    "D40000_N50": {
      "cluster_parallel_sec": 111.9505,
      "computation_sec": 5.9305,
      "scheduling_sec": 104.86,
      "cluster_init_sec": 50.9895,
      "wall_clock_sec": 167.6175,
      "cost_usd": 0.0082,
      "n_reps": 10
    },
    "D40000_N75": {
      "cluster_parallel_sec": 138.231,
      "computation_sec": 3.963,
      "scheduling_sec": 133.5445,
      "cluster_init_sec": 45.076,
      "wall_clock_sec": 191.8555,
      "cost_usd": 0.0089,
      "n_reps": 10
    },
    "D50000_N100": {
      "cluster_parallel_sec": 169.799,
      "computation_sec": 3.7435,
      "scheduling_sec": 165.335,
      "cluster_init_sec": 39.2415,
      "wall_clock_sec": 229.311,
      "cost_usd": 0.0112,
      "n_reps": 10
    },
    "D50000_N125": {
      "cluster_parallel_sec": 163.5525,
      "computation_sec": 3.0215,
      "scheduling_sec": 159.3295,
      "cluster_init_sec": 40.5235,
      "wall_clock_sec": 213.8445,
      "cost_usd": 0.0119,
      "n_reps": 10
    },
    "D50000_N25": {
      "cluster_parallel_sec": 105.1055,
      "computation_sec": 14.848,
      "scheduling_sec": 89.2045,
      "cluster_init_sec": 42.9915,
      "wall_clock_sec": 152.245,
      "cost_usd": 0.0091,
      "n_reps": 10
    },
    "D50000_N50": {
      "cluster_parallel_sec": 112.733,
      "computation_sec": 7.384,
      "scheduling_sec": 104.197,
      "cluster_init_sec": 47.083,
      "wall_clock_sec": 165.0445,
      "cost_usd": 0.0098,
      "n_reps": 10
    },
    "D50000_N75": {
      "cluster_parallel_sec": 168.1885,
      "computation_sec": 4.9725,
      "scheduling_sec": 162.053,
      "cluster_init_sec": 42.0305,
      "wall_clock_sec": 218.9925,
      "cost_usd": 0.0105,
      "n_reps": 10
    },
    "D5000_N100": {
      "cluster_parallel_sec": 143.107,
      "computation_sec": 0.37,
      "scheduling_sec": 141.6815,
      "cluster_init_sec": 46.806,
      "wall_clock_sec": 199.743,
      "cost_usd": 0.0033,
      "n_reps": 10
    },
    "D5000_N125": {
      "cluster_parallel_sec": 183.1435,
      "computation_sec": 0.302,
      "scheduling_sec": 181.7975,
      "cluster_init_sec": 40.311,
      "wall_clock_sec": 235.501,
      "cost_usd": 0.004,
      "n_reps": 10
    },
    "D5000_N25": {
      "cluster_parallel_sec": 37.967,
      "computation_sec": 1.424,
      "scheduling_sec": 35.5335,
      "cluster_init_sec": 53.936,
      "wall_clock_sec": 93.9765,
      "cost_usd": 0.0014,
      "n_reps": 10
    },
    "D5000_N50": {
      "cluster_parallel_sec": 72.5685,
      "computation_sec": 0.723,
      "scheduling_sec": 70.8285,
      "cluster_init_sec": 47.8965,
      "wall_clock_sec": 128.5085,
      "cost_usd": 0.0021,
      "n_reps": 10
    },
    "D5000_N75": {
      "cluster_parallel_sec": 108.145,
      "computation_sec": 0.4995,
      "scheduling_sec": 106.6625,
      "cluster_init_sec": 50.5995,
      "wall_clock_sec": 166.3285,
      "cost_usd": 0.0027,
      "n_reps": 10
    }
  },
  "micro_grid_low_n_low_ondemand": {}
}
```

### 11.9 — Overnight Spot low nested (D → N → metrics)

```json
{
  "5000": {
    "25": {
      "wall_clock_sec": 93.9765,
      "cluster_parallel_sec": 37.967,
      "computation_sec": 1.424,
      "cost_usd": 0.0014,
      "n_reps": 10
    },
    "50": {
      "wall_clock_sec": 128.5085,
      "cluster_parallel_sec": 72.5685,
      "computation_sec": 0.723,
      "cost_usd": 0.0021,
      "n_reps": 10
    },
    "75": {
      "wall_clock_sec": 166.3285,
      "cluster_parallel_sec": 108.145,
      "computation_sec": 0.4995,
      "cost_usd": 0.0027,
      "n_reps": 10
    },
    "100": {
      "wall_clock_sec": 199.743,
      "cluster_parallel_sec": 143.107,
      "computation_sec": 0.37,
      "cost_usd": 0.0033,
      "n_reps": 10
    },
    "125": {
      "wall_clock_sec": 235.501,
      "cluster_parallel_sec": 183.1435,
      "computation_sec": 0.302,
      "cost_usd": 0.004,
      "n_reps": 10
    }
  },
  "10000": {
    "25": {
      "wall_clock_sec": 85.92,
      "cluster_parallel_sec": 31.5155,
      "computation_sec": 2.9885,
      "cost_usd": 0.0024,
      "n_reps": 10
    },
    "50": {
      "wall_clock_sec": 117.9685,
      "cluster_parallel_sec": 60.4005,
      "computation_sec": 1.511,
      "cost_usd": 0.0032,
      "n_reps": 10
    },
    "75": {
      "wall_clock_sec": 147.4285,
      "cluster_parallel_sec": 90.908,
      "computation_sec": 1.015,
      "cost_usd": 0.0038,
      "n_reps": 10
    },
    "100": {
      "wall_clock_sec": 185.4425,
      "cluster_parallel_sec": 104.49,
      "computation_sec": 0.787,
      "cost_usd": 0.0049,
      "n_reps": 10
    },
    "125": {
      "wall_clock_sec": 189.48,
      "cluster_parallel_sec": 130.0025,
      "computation_sec": 0.669,
      "cost_usd": 0.0058,
      "n_reps": 10
    }
  },
  "20000": {
    "25": {
      "wall_clock_sec": 126.994,
      "cluster_parallel_sec": 74.839,
      "computation_sec": 5.9215,
      "cost_usd": 0.0041,
      "n_reps": 10
    },
    "50": {
      "wall_clock_sec": 118.8955,
      "cluster_parallel_sec": 66.3135,
      "computation_sec": 3.078,
      "cost_usd": 0.0048,
      "n_reps": 10
    },
    "75": {
      "wall_clock_sec": 150.826,
      "cluster_parallel_sec": 92.5535,
      "computation_sec": 2.085,
      "cost_usd": 0.0058,
      "n_reps": 10
    },
    "100": {
      "wall_clock_sec": 176.976,
      "cluster_parallel_sec": 122.9845,
      "computation_sec": 1.554,
      "cost_usd": 0.0064,
      "n_reps": 10
    },
    "125": {
      "wall_clock_sec": 214.459,
      "cluster_parallel_sec": 153.993,
      "computation_sec": 1.2405,
      "cost_usd": 0.0071,
      "n_reps": 10
    }
  },
  "30000": {
    "25": {
      "wall_clock_sec": 115.9795,
      "cluster_parallel_sec": 68.554,
      "computation_sec": 8.973,
      "cost_usd": 0.0058,
      "n_reps": 10
    },
    "50": {
      "wall_clock_sec": 162.8095,
      "cluster_parallel_sec": 110.922,
      "computation_sec": 4.573,
      "cost_usd": 0.0066,
      "n_reps": 10
    },
    "75": {
      "wall_clock_sec": 155.6335,
      "cluster_parallel_sec": 103.744,
      "computation_sec": 3.045,
      "cost_usd": 0.0073,
      "n_reps": 10
    },
    "100": {
      "wall_clock_sec": 173.2455,
      "cluster_parallel_sec": 123.122,
      "computation_sec": 2.2555,
      "cost_usd": 0.008,
      "n_reps": 10
    },
    "125": {
      "wall_clock_sec": 211.332,
      "cluster_parallel_sec": 154.3045,
      "computation_sec": 1.8305,
      "cost_usd": 0.0088,
      "n_reps": 10
    }
  },
  "40000": {
    "25": {
      "wall_clock_sec": 128.8085,
      "cluster_parallel_sec": 80.9075,
      "computation_sec": 11.8355,
      "cost_usd": 0.0075,
      "n_reps": 10
    },
    "50": {
      "wall_clock_sec": 167.6175,
      "cluster_parallel_sec": 111.9505,
      "computation_sec": 5.9305,
      "cost_usd": 0.0082,
      "n_reps": 10
    },
    "75": {
      "wall_clock_sec": 191.8555,
      "cluster_parallel_sec": 138.231,
      "computation_sec": 3.963,
      "cost_usd": 0.0089,
      "n_reps": 10
    },
    "100": {
      "wall_clock_sec": 192.127,
      "cluster_parallel_sec": 134.8955,
      "computation_sec": 2.9825,
      "cost_usd": 0.0097,
      "n_reps": 10
    },
    "125": {
      "wall_clock_sec": 217.403,
      "cluster_parallel_sec": 154.896,
      "computation_sec": 2.4145,
      "cost_usd": 0.0104,
      "n_reps": 10
    }
  },
  "50000": {
    "25": {
      "wall_clock_sec": 152.245,
      "cluster_parallel_sec": 105.1055,
      "computation_sec": 14.848,
      "cost_usd": 0.0091,
      "n_reps": 10
    },
    "50": {
      "wall_clock_sec": 165.0445,
      "cluster_parallel_sec": 112.733,
      "computation_sec": 7.384,
      "cost_usd": 0.0098,
      "n_reps": 10
    },
    "75": {
      "wall_clock_sec": 218.9925,
      "cluster_parallel_sec": 168.1885,
      "computation_sec": 4.9725,
      "cost_usd": 0.0105,
      "n_reps": 10
    },
    "100": {
      "wall_clock_sec": 229.311,
      "cluster_parallel_sec": 169.799,
      "computation_sec": 3.7435,
      "cost_usd": 0.0112,
      "n_reps": 10
    },
    "125": {
      "wall_clock_sec": 213.8445,
      "cluster_parallel_sec": 163.5525,
      "computation_sec": 3.0215,
      "cost_usd": 0.0119,
      "n_reps": 10
    }
  }
}
```

### 11.10 — Local batch result JSON files

```json
{
  "local_batch_result_files": [
    "experiments/results/probe_d10k_low_n_spot_20260713_214728/batch_compute_only_20260713_214728.json",
    "experiments/results/probe_d50k_pow2_ondemand_20260714_083435/batch_compute_only_20260714_083435.json",
    "experiments/results/probe_d50k_pow2_ondemand_low_20260714_130755/batch_compute_only_20260714_130755.json",
    "experiments/results/probe_d50k_pow2_ondemand_medium_20260714_140126/batch_compute_only_20260714_140127.json",
    "experiments/results/probe_d50k_pow2_spot_20260713_222446/batch_compute_only_20260713_222446.json",
    "experiments/results/probe_d50k_pow2_spot_low_20260714_090237/batch_compute_only_20260714_090238.json",
    "experiments/results/probe_d50k_pow2_spot_medium_20260714_095725/batch_compute_only_20260714_095725.json"
  ],
  "local_batch_result_counts": {
    "experiments/results/probe_d10k_low_n_spot_20260713_214728/batch_compute_only_20260713_214728.json": 9,
    "experiments/results/probe_d50k_pow2_ondemand_20260714_083435/batch_compute_only_20260714_083435.json": 1,
    "experiments/results/probe_d50k_pow2_ondemand_low_20260714_130755/batch_compute_only_20260714_130755.json": 14,
    "experiments/results/probe_d50k_pow2_ondemand_medium_20260714_140126/batch_compute_only_20260714_140127.json": 14,
    "experiments/results/probe_d50k_pow2_spot_20260713_222446/batch_compute_only_20260713_222446.json": 5,
    "experiments/results/probe_d50k_pow2_spot_low_20260714_090237/batch_compute_only_20260714_090238.json": 14,
    "experiments/results/probe_d50k_pow2_spot_medium_20260714_095725/batch_compute_only_20260714_095725.json": 14
  }
}
```

*End of handoff. For full replication history (Sheets formula crisis, compute_only grids, metric definitions), see `experiments/docs/HANDOFF_CLAUDE.md` and `experiments/docs/FINAL_REPORT.md`.*
