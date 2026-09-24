# PLAN.md — Research runbook (long jobs, full control)

Project: **chemoinformatics-descriptor-computation**  
Paper: *Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics*  
Environment: `conda activate venv_chemoinformatics` — then `export PYTHONPATH=.` from repo root.

This file is the **single checklist** for multi-hour AWS Batch runs: estimation → human gate → execution → verification → optional model fit.

**Full analytical breakdown** (purpose, inputs/outputs, success criteria per substep): **`docs/ANALYTICAL_STEPS.md`**.

---

## Step 0 — Preconditions

- [ ] `.env` from `.env.example` (AWS, `S3_BUCKET`, `AWS_BATCH_JOB_QUEUE`, `AWS_BATCH_JOB_DEFINITION`, optional `GOOGLE_SHEETS_ID`)
- [ ] EC2-backed queue for paper-style **N** scaling (e.g. `chemo-ec2-queue`) — see `docs/options.md`
- [ ] Datasets generated for every `(D, complexity)` in your YAML:

```bash
PYTHONPATH=. python datasets/generators/smiles_generator.py \
  --sizes 5000 10000 20000 30000 40000 50000 \
  --complexity low \
  --output-dir datasets/samples
```

- [ ] `python scripts/validate_setup.py` — green for packages and directories

---

## Step 1 — Estimation only (no AWS spend)

**Rule:** Never start a large Batch run without reviewing estimator output.

### 1A — Email pilot (5 configurations from March 2026 table)

```bash
PYTHONPATH=. python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/paper_email_table_march2026_compute.yaml \
  --dataset-dir datasets/samples --verbose

PYTHONPATH=. python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/paper_email_table_march2026_full.yaml \
  --dataset-dir datasets/samples --verbose
```

Each run saves `experiments/results/estimate_*.json`. Note `total_time_hours` and `total_cost_usd`.

### 1B — Full paper grids (42 jobs each)

```bash
PYTHONPATH=. python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/paper_replication_low_compute_only.yaml \
  --dataset-dir datasets/samples --verbose \
  --save experiments/results/estimate_paper_compute_PREFLIGHT.json

PYTHONPATH=. python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/paper_replication_low_full_pipeline.yaml \
  --dataset-dir datasets/samples --verbose \
  --save experiments/results/estimate_paper_full_PREFLIGHT.json
```

**Checkpoint:** If totals look wrong, stop and adjust YAML (`node_configs`, `dataset_sizes`) or fitted model (`--model experiments/results/fitted_model.json`) before Step 2.

---

## Step 2 — Human gate (you decide)

- [ ] I reviewed both preflight JSON files  
- [ ] I am OK with wall-clock order of magnitude (Batch queue + 84 jobs total for both grids if you run everything)  
- [ ] I will monitor the AWS Batch console / CloudWatch during the run  

**Do not proceed to Step 3 until you explicitly confirm.**

---

## Step 3 — Run experiments (hours)

Run **one YAML at a time** so you can stop between compute_only and full_pipeline.

### 3A — Email pilot (quick sanity)

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/paper_email_table_march2026_compute.yaml

PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/paper_email_table_march2026_full.yaml
```

### 3B — Full paper grids

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/paper_replication_low_compute_only.yaml

PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/paper_replication_low_full_pipeline.yaml
```

Outputs land in `experiments/results/` as `batch_<mode>_<timestamp>.json` (and per-run folders for ad-hoc CLI runs).

**Optional:** `./scripts/paper_research_runbook.sh` runs validation + both estimations + interactive pauses before each Batch config.

**Rough duration:** depends on queue depth, Spot availability, and D/N; treat as **multi-hour** for the full 84-job suite.

---

## Step 4 — Verify estimation vs actual (loss)

For each **estimate** JSON, pair it with the **matching** Batch result JSON from Step 3 (same configs / same D×N grid).

```bash
PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --estimate experiments/results/estimate_paper_compute_PREFLIGHT.json \
  --actual experiments/results/batch_compute_only_<YOUR_RUN>.json \
  --json-out experiments/results/verification_compute_<DATE>.json

PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --estimate experiments/results/estimate_paper_full_PREFLIGHT.json \
  --actual experiments/results/batch_full_pipeline_<YOUR_RUN>.json \
  --json-out experiments/results/verification_full_<DATE>.json
```

Interpretation:

- **`--metric auto`**: `computation_sec` for `compute_only` rows; `total_pipeline_sec` for `full_pipeline` (aligns estimator phases with what you measure).
- **`--metric cost_usd`**: cost comparison only.

**Checkpoint:** Record MAE/MAPE; large gaps mean revisit `src/core/model.py` coefficients or estimator heuristics in `experiment_estimator.py`.

---

## Step 5 — Fit \(T(N,D)\) from data (after you trust the runs)

```bash
python src/core/model.py fit
python src/core/model.py optimal-table
```

Use `experiments/results/fitted_model.json` in future `--model` for the estimator.

---

## Quick reference — commands from README

| Goal | Command |
|------|---------|
| Estimator | `python experiments/estimator/experiment_estimator.py --config <yaml> --dataset-dir datasets/samples` |
| Batch run | `python experiments/run_experiment.py --config <yaml>` |
| Local run | `python experiments/run_experiment.py --local ...` |
| Loss report | `python experiments/verify_estimate_vs_actual.py --estimate ... --actual ...` |

---

## Status tracker (edit as you go)

| Stage | Status | Notes |
|-------|--------|--------|
| Datasets on disk | ⬜ | |
| Preflight estimates saved | ⬜ | |
| Human approval | ⬜ | |
| Batch compute_only | ⬜ | |
| Batch full_pipeline | ⬜ | |
| Verification JSONs | ⬜ | |
| Model fit | ⬜ | |

---

## Key files

```
experiments/estimator/experiment_estimator.py   # Pre-run estimates
experiments/run_experiment.py                   # Local + Batch
experiments/verify_estimate_vs_actual.py        # Estimate vs actual loss
experiments/configs/paper_replication_low_*.yaml
scripts/paper_research_runbook.sh
src/core/model.py
```
