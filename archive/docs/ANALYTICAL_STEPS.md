# Analytical steps — end-to-end research runbook

This document is the **exhaustive, ordered** procedure for replicating and extending the paper’s experiments on AWS Batch, with **explicit purpose**, **inputs/outputs**, and **success criteria** at each stage.  
Shorter checklist: **`docs/PLAN.md`**. Commands assume repo root and `export PYTHONPATH=.` (or `PYTHONPATH=. python …`).

---

## A. Scope and ordering (why this sequence)

| Order | Stage | Rationale |
|------|--------|-----------|
| 1 | Environment + identity | Wrong region or IAM user ⇒ silent failures or `AccessDenied` after long waits. |
| 2 | Local validation | Catches missing Python packages / folders before any cloud cost. |
| 3 | Dataset files on disk | Batch jobs read SMILES from S3; local CSVs must exist to upload. |
| 5 | **Human checkpoint** | Research judgment: grid too large, wrong queue, or cost unacceptable. |
| 6 | Batch execution | Mutates cloud state, consumes time and money; irreversible except by stopping jobs. |
| 7 | Estimate vs actual | Quantifies model calibration error (MAE / MAPE / RMSE). |
| 8 | Fit \(T(N,D)\) from data | Replaces paper default coefficients with **your** infrastructure’s reality. |

---

## B. Phase 0 — Shell and Python environment

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| B.0.1 | `conda activate venv_chemoinformatics` | Fixed dependency set for the repo. | `which python` points inside env. |
| B.0.2 | `cd /path/to/chemoinformatics-descriptor-computation` | Relative paths (`datasets/`, `experiments/`) resolve. | `ls experiments/run_experiment.py` exists. |
| B.0.3 | `export PYTHONPATH=.` (or prefix each command) | Imports `src.*`, `experiments.*` without installing as package. | `python -c "import src.core.model"` exits 0. |

---

## C. Phase 1 — Secrets and configuration (no execution yet)

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| C.1.1 | Copy `.env.example` → `.env` if needed; edit **never committed**. | Supplies `boto3`, Sheets, S3, Batch names. | `.gitignore` contains `.env`; `git status` does not list `.env`. |
| C.1.2 | Set `AWS_REGION` (e.g. `eu-central-1`) to match **Batch + S3** region. | Cross-region Batch/S3 calls fail or add latency. | Region matches console top-right for Batch. |
| C.1.3 | Set `AWS_S3_BUCKET` (or `S3_BUCKET` per code paths) to your upload bucket. | `run_experiment` uploads `smiles_*.csv` before jobs. | Bucket exists; your IAM user can `s3:PutObject`. |
| C.1.4 | Set `AWS_BATCH_JOB_QUEUE` and `AWS_BATCH_JOB_DEFINITION` to **EC2** queue/def if you want paper-style **N** (array path when queue name contains `ec2`). | Fargate-only setups may not scale **N** as distinct workers. | Console: queue state **Valid**, definition **Active**. |
| C.1.5 | Optional: `GOOGLE_SHEETS_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`. | Streams estimates/results to Sheets. | JSON path exists; sheet shared with service account email. |

---

## D. Phase 2 — Identity and local validation

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| D.2.1 | `aws sts get-caller-identity` | Confirms **which** IAM principal pays for and submits jobs. | JSON shows expected `Account` and `Arn`. |
| D.2.2 | `python scripts/validate_setup.py` | Loads `.env`; checks packages, dirs, AWS (env or default chain), Sheets id. | All lines **SUCCESS** (warnings acceptable only if you intentionally omit Sheets). |

**Analytical note:** If CLI identity (`rekognition-emotion-app`) differs from keys in `.env`, `boto3` order is: env vars override profile. Know which identity Batch runs under — it must have **Batch SubmitJob**, **S3** on your prefix, and **PassRole** if job roles are restricted.

---

## E. Phase 3 — Dataset generation (disk artifacts)

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| E.3.1 | For each YAML `dataset_sizes` × `smiles_complexity`, ensure file `datasets/samples/smiles_{D}_{complexity}.csv` exists with column `smiles`. | Runner raises `FileNotFoundError` if missing. | `ls datasets/samples/smiles_*_{low\|medium\|high}.csv` covers all D in config. |
| E.3.2 | Example generator invocation: | | |
| | `PYTHONPATH=. python datasets/generators/smiles_generator.py --sizes 5000 10000 … --complexity low --output-dir datasets/samples` | Reproducible synthetic corpora; length distribution encodes “low/medium/high”. | CSV row count equals requested D; mean SMILES length matches generator design. |

---

## F. Phase 4 — Estimation only (preflight, **no** Batch jobs)

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| F.4.1 | `PYTHONPATH=. python experiments/estimator/experiment_estimator.py --config <yaml> --dataset-dir datasets/samples [--verbose] [--save path.json]` | Uses `ModelCoefficients` (\(T(N,D)\)) + phase heuristics (S3, cluster init, sync); reads **real** CSV stats when `--dataset-dir` set. | Console shows per-(D,N) table; file `experiments/results/estimate_*.json` written. |
| F.4.2 | Record for each planned run: `total_time_sec`, `total_cost_usd`, `n_jobs` from summary JSON. | Compare to calendar and budget. | Numbers within acceptable research budget. |
| F.4.3 | Optional: `--model experiments/results/fitted_model.json` after you have fitted once. | Estimates use **empirical** coefficients instead of paper defaults. | File exists from Phase H. |

**Recommended order of YAMLs:**

1. **Pilot (5 configs total):**  
   `paper_email_table_march2026_compute.yaml` then `paper_email_table_march2026_full.yaml`
2. **Full grids (42 + 42 jobs):**  
   `paper_replication_low_compute_only.yaml` then `paper_replication_low_full_pipeline.yaml`

---

## G. Phase 5 — Human gate (mandatory pause)

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| G.5.1 | Open saved `estimate_*.json`; scan `per_config` for outliers. | Catch mis-typed `node_configs` or wrong complexity. | No impossible N; costs order-of-magnitude plausible. |
| G.5.2 | In AWS console: compute environment has capacity; no stuck INVALID queues. | Avoids hours of `RUNNABLE` with no instances. | Queue **Valid**; CE not `DISABLED`. |
| G.5.3 | **Explicit decision:** proceed / shrink grid / stop. | Research control. | Written note or ticket for traceability. |

---

## H. Phase 6 — Batch execution (`run_experiment.py` without `--local`)

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| H.6.1 | `load_dotenv` runs inside `main()`; ensure cwd is repo root so `.env` loads. | Picks up `AWS_*`, `S3_*`, `AWS_BATCH_*`. | No immediate `SystemExit` on missing env. |
| H.6.2 | `PYTHONPATH=. python experiments/run_experiment.py --config <same_yaml_as_estimate>` | For each (D,N): upload shards / full CSV to S3; submit Batch job(s); poll until **SUCCEEDED** or **FAILED**; append Sheets; write JSON row. | File `experiments/results/batch_<mode>_<timestamp>.json` contains one object per (D,N) with `status`, `total_pipeline_sec`, `computation_sec`, `cost_usd`. |
| H.6.3 | Monitor Batch **Jobs** UI for failures; note `job_id` from JSON for CloudWatch logs. | Debug container, IAM, OOM. | All rows `status: SUCCEEDED` for that run. |
| H.6.4 | Run **one YAML at a time** if you want a clean stop between `compute_only` and `full_pipeline`. | Reduces blast radius. | Two separate JSON outputs if you split. |

**Analytical mapping — modes:**

- **`compute_only`:** Measures primarily descriptor wall-clock on workers; orchestration phases may be minimal in JSON — verification script compares **`computation_sec`** in auto mode.
- **`full_pipeline`:** Includes cluster init, scheduling, S3, sync — aligns with paper “total execution time”; verification compares **`total_pipeline_sec`** in auto mode.

---

## I. Phase 7 — Verification (estimator vs actual)

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| I.7.1 | Pair files: **same** `dataset_sizes`, `node_configs`, complexity as the estimate run. | Otherwise join keys (D,N) mismatch. | `n_matched` in report equals number of (D,N) pairs. |
| I.7.2 | `PYTHONPATH=. python experiments/verify_estimate_vs_actual.py --estimate <estimate.json> --actual <batch.json> [--metric auto\|cost_usd] [--json-out …]` | **auto:** `computation_sec` if actual `mode` is `compute_only`, else `total_pipeline_sec`. | JSON report with `loss.mae`, `loss.mape_pct`, `per_row`. |
| I.7.3 | Interpret MAPE: large error on small D is expected (overhead-dominated regime); check systematic bias (always over/under). | Guides refit or estimator heuristic tuning. | Documented in lab notebook / thesis appendix. |

---

## J. Phase 8 — Model fitting from collected results

| Step | Action | Purpose | Success criterion |
|------|--------|---------|-------------------|
| J.8.1 | Ensure result JSONs are under `experiments/results/`; `load_results_for_fitting` skips `estimate*` files. | OLS fit for \(a,b,c,d,e\) in `fit_model`. | `python src/core/model.py fit` writes `fitted_model.json`. |
| J.8.2 | Inspect printed **R²**; if \(d \le 0\), model not convex — check data or subset. | Required for analytical \(N^*(D)\). | `d > 0` in saved JSON. |
| J.8.3 | `python src/core/model.py optimal-table` | Tabulates \(N^*(D)\) from fitted or default model. | Table printed for thesis/paper. |
| J.8.4 | Re-run estimator with `--model experiments/results/fitted_model.json` for future grids. | Closed-loop planning. | New estimates closer to recent runs. |

---

## K. Artifact map (what file proves what)

| Artifact | Produced by | Contains |
|----------|-------------|----------|
| `datasets/samples/smiles_{D}_{complexity}.csv` | `smiles_generator.py` | Input structures |
| `experiments/results/estimate_*.json` | `experiment_estimator.py` | `per_config`, totals, `optimal_nodes` |
| `experiments/results/batch_*.json` | `run_experiment.py` (Batch) | Measured phases, `job_id`, `cost_usd` |
| `experiments/results/verification_*.json` | `verify_estimate_vs_actual.py` | MAE, MAPE, per-row errors |
| `experiments/results/fitted_model.json` | `src/core/model.py fit` | Coefficients + R² |

---

## L. Optional orchestration script

`scripts/paper_research_runbook.sh` — runs `validate_setup`, both paper-grid **estimates**, then **interactive** `read` pauses before each long Batch invocation. Use when you want shell-level gates without editing this doc.

---

## M. Traceability checklist (copy into lab notes)

- [ ] Date / operator name  
- [ ] `aws sts` ARN used for Batch  
- [ ] Estimator JSON paths (preflight)  
- [ ] Human “proceed” timestamp  
- [ ] Batch result JSON paths  
- [ ] Verification JSON paths  
- [ ] Fitted model revision (if any)  

---

*End of analytical steps. For shorter commands-only flow, see `README.md` and `docs/PLAN.md`.*
