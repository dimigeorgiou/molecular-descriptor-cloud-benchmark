# Chemoinformatics descriptor computation (distributed)

Research codebase for **optimal resource allocation** when computing molecular descriptors at scale on **AWS Batch**, aligned with the paper *Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics* (performance model \(T(N,D)=a+bN+cD+dN^2+eND\), analytical \(N^*(D)\), and empirical validation).

## Environment

**Recommended (includes RDKit):**

```bash
conda env create -f environment.yml   # or: conda activate venv_chemoinformatics
conda activate venv_chemoinformatics
cd /path/to/chemoinformatics-descriptor-computation
export PYTHONPATH=.
```

**Pip-only (orchestrator / Sheets / tests; RDKit still via conda):**

```bash
pip install -r requirements.txt                 # core
pip install -r requirements-analysis.txt        # optional plotting (matplotlib/scipy)
conda install -c conda-forge rdkit              # required for descriptor workers
```

Copy secrets template and fill in AWS, S3, Batch queue/job definition, and optional Google Sheets:

```bash
cp .env.example .env
# Never commit .env or config/google_service_account.json (see .gitignore)
```

### Connecting to AWS (credentials)

**Do not share access keys** in chat, email, or Git. If a key is ever exposed, **rotate it** in IAM immediately.

You can authenticate in either of these ways (both work with `boto3` used by this project):

**Option A — AWS CLI profiles (recommended on your laptop)**  
Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), then:

```bash
aws configure
# AWS Access Key ID: <paste from IAM>
# AWS Secret Access Key: <paste>
# Default region name: eu-central-1   # or your Batch/S3 region
# Default output format: json
```

Credentials are stored in `~/.aws/credentials` and region in `~/.aws/config`. The CLI and Python both pick them up automatically.

**Option B — `.env` in the repo (loaded by the estimator and `run_experiment.py`)**  
Edit `.env` (gitignored) with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION` (or `AWS_DEFAULT_REGION`) matching your account. `python-dotenv` loads `.env` when you run `experiments/estimator/experiment_estimator.py` and `experiments/run_experiment.py`.

**Verify the session:**

```bash
aws sts get-caller-identity
```

You should see your account ID and ARN. If this fails, fix credentials or region before running Batch experiments.

Preflight: loads **`.env`** from the repo root, checks Python packages and directories, then AWS (env keys **or** default chain like `~/.aws/credentials`) and `GOOGLE_SHEETS_ID`.

```bash
python scripts/validate_setup.py
```

If `aws sts get-caller-identity` works but this script used to warn on AWS, run it again from the project directory after the script update — it now mirrors how `boto3` resolves credentials.

## Research workflow (recommended order)

1. **Generate SMILES datasets** (sizes and complexity must match your YAML).
2. **Run the estimator** for the same YAML (time/cost *before* spending AWS budget).
3. **Review** printed totals and saved `experiments/results/estimate_*.json`.
4. **Run experiments** (`--local` for dev, or Batch for paper-scale).
5. **Verify loss** between estimate and actual with `experiments/verify_estimate_vs_actual.py`.

See **`docs/PLAN.md`** for a full runbook with checkpoints, wall-clock expectations, and verification commands.  
For a **step-by-step analytical** version (tables: rationale, inputs, outputs, success criteria), see **`docs/ANALYTICAL_STEPS.md`**.

## Dataset generation

Example (low complexity, single size):

```bash
PYTHONPATH=. python datasets/generators/smiles_generator.py \
  --sizes 1000 \
  --complexity low \
  --output-dir datasets/samples
```

Full paper-style grid (low complexity, ~32 char avg; paper discussion often uses ~57 for medium):

```bash
PYTHONPATH=. python datasets/generators/smiles_generator.py \
  --sizes 5000 10000 20000 30000 40000 50000 \
  --complexity low \
  --output-dir datasets/samples
```

Files must follow `datasets/samples/smiles_{D}_{complexity}.csv` with a `smiles` column.

## Experiment estimation (always before large Batch runs)

```bash
PYTHONPATH=. python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/paper_replication_low_full_pipeline.yaml \
  --dataset-dir datasets/samples \
  --verbose
```

- Writes **`experiments/results/estimate_<config_stem>_<timestamp>.json`** automatically.
- Optional explicit path: `--save experiments/results/my_estimate.json`
- Optional fitted model: `--model experiments/results/fitted_model.json`
- Google Sheets: appends are **throttled** (default **2.5s** between rows) and reuse one worksheet handle; override with **`SHEETS_APPEND_INTERVAL_SEC`** in `.env` if you still see `429` quota errors.

## Running experiments

### Local (no AWS)

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --local \
  --name exp_5000_low_local \
  --smiles-complexity low \
  --dataset-sizes 1000 \
  --node-configs 25 50 \
  --mode compute_only \
  --dataset-dir datasets/samples
```

### AWS Batch (same flags via ad-hoc config)

Requires `S3_BUCKET`/`AWS_S3_BUCKET`, `BATCH_JOB_QUEUE`/`AWS_BATCH_JOB_QUEUE`, `BATCH_JOB_DEFINITION`/`AWS_BATCH_JOB_DEFINITION` (see `.env.example`). For EC2-backed queues whose name contains `ec2`, the runner uses the **array-job / multi-shard** path so `N` reflects parallel workers.

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --name exp_1000_low_batch \
  --smiles-complexity low \
  --dataset-sizes 1000 \
  --node-configs 25 50 \
  --mode compute_only \
  --dataset-dir datasets/samples
```

### YAML-driven (paper replication)

- **Full paper grid (compute_only)** — 6×7 = 42 jobs:  
  `experiments/configs/paper_replication_low_compute_only.yaml`
- **Full paper grid (full_pipeline)** — 42 jobs:  
  `experiments/configs/paper_replication_low_full_pipeline.yaml`
- **Email pilot subsets** (March 2026 table):  
  `paper_email_table_march2026_compute.yaml`, `paper_email_table_march2026_full.yaml`
- **Same paper grid, medium SMILES** (~57 char target — closer to paper narrative):  
  `paper_replication_medium_compute_only.yaml`, `paper_replication_medium_full_pipeline.yaml`  
  (requires `smiles_{D}_medium.csv`; generate with `--complexity medium`.)

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/paper_replication_low_full_pipeline.yaml \
  --dataset-dir datasets/samples
```

Each run creates **`experiments/results/<config_name>_<timestamp>/`** with:

- **`config.yaml`** — copy of the YAML you passed (frozen for that run)
- **`estimation/estimate.json`** — estimator output *before* Batch/local work (for `verify_estimate_vs_actual.py`)
- **`batch_<mode>_<timestamp>.json`** or **`local_<mode>_<timestamp>.json`** — actual timings
- **Plots** (`panel_*.png`) when matplotlib is available

Skip the pre-run estimate with **`--skip-pre-estimate`** or env **`SKIP_PRE_RUN_ESTIMATE=1`** (e.g. quick retries).

Interactive orchestration (estimate → pause → run both grids):

```bash
chmod +x scripts/paper_research_runbook.sh
./scripts/paper_research_runbook.sh
```

## Verify estimator accuracy vs actual results

### A. Same run folder (recommended after `run_experiment.py --config …`)

```bash
PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --run-dir experiments/results/paper_replication_low_full_pipeline_20260418_120000 \
  --json-out experiments/results/verification_that_run.json
```

### B. Legacy paths (standalone estimate JSON + flat result JSON)

```bash
PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --estimate experiments/results/estimate_paper_replication_low_full_pipeline_20260101_120000.json \
  --actual experiments/results/batch_full_pipeline_20260101_121500.json \
  --json-out experiments/results/verification_full_20260101.json
```

### C. Many runs at once

All directories matching a glob under `experiments/results/`:

```bash
PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --runs-glob 'paper_replication_low_full_pipeline_*' \
  --json-out experiments/results/verification_batch_low_full.json
```

All runs whose folder name starts with the **`name:`** in a config file:

```bash
PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --from-config experiments/configs/paper_replication_low_full_pipeline.yaml \
  --json-out experiments/results/verification_by_config_name.json
```

One **standalone** estimate JSON vs many **`exp_*`** folders (prints a summary table automatically):

```bash
PYTHONPATH=. python experiments/verify_estimate_vs_actual.py \
  --estimate experiments/results/estimate_paper_replication_low_compute_only_20260418_000202.json \
  --runs-parent experiments/results \
  --runs-glob 'exp_*_20260318_*' \
  --json-out experiments/results/verification_batch.json
```

Add **`--print-table`** when using co-located `estimation/estimate.json` only and you still want the markdown table.

- **`--metric auto`** (default): compares `computation_sec` when actual `mode` is `compute_only`, and `total_pipeline_sec` when `mode` is `full_pipeline` (fair vs estimator phases).
- **`--metric cost_usd`**: compares `estimated_cost_usd` to `cost_usd`.

Output includes **MAE, RMSE, MAPE**, and per-(D,N) rows. Multi-run mode prints a JSON object with a **`runs`** array (each entry has `run_dir`, paths, `report`, or `error`).

## Model fitting (optional)

After collecting result JSON files under `experiments/results/`:

```bash
python src/core/model.py fit
python src/core/model.py optimal-table
```

Fitted coefficients are written to `experiments/results/fitted_model.json` when using `fit`.

## Key directories

| Path | Role |
|------|------|
| `src/core/model.py` | \(T(N,D)\), `fit_model`, `optimal_nodes` |
| `experiments/run_experiment.py` | Local + Batch runner |
| `experiments/estimator/experiment_estimator.py` | Pre-run cost/time estimation |
| `experiments/verify_estimate_vs_actual.py` | Estimate vs actual loss (`--run-dir`, `--runs-glob`, `--from-config`) |
| `experiments/results/<name>_<ts>/estimation/estimate.json` | Pre-run estimate co-located with that experiment |
| `experiments/configs/` | YAML experiment definitions |
| `experiments/results/` | Estimates, batch outputs, verification reports |
| `docs/options.md` | AWS Batch patterns (EC2 vs Fargate vs array jobs) |

## AWS resources (after you are logged in)

- **Region** must match Batch and S3 (e.g. `eu-central-1`). Set `AWS_REGION` or `AWS_DEFAULT_REGION` in `.env`, or in `aws configure`.
- **Queue / job definition** names must match the console (e.g. `chemo-ec2-queue`, `chemo-ec2-worker`).
- **Job definition image**: use a container that includes your real descriptor stack (RDKit, etc.); generic Amazon Linux images are only for plumbing tests.

## Citation

Research context and notation follow the project paper (Didachos, Georgiou, Fousteris, Kanavos). Use `docs/PLAN.md` and `docs/options.md` for experiment discipline and infrastructure semantics.
