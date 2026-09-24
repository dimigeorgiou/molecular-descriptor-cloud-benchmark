# Research brief — chemoinformatics-descriptor-computation (for LLM / Claude Fast context)

**Paste this block into project instructions** when you need the model to understand *what this repo is for* without reading the whole README.

---

## One-sentence pitch

This repository implements **empirical and analytical work for optimal parallel scheduling** of **molecular descriptor computation** (SMILES → descriptors) on **AWS Batch**: it fits a runtime model \(T(N,D)\), derives an analytical optimum \(N^*(D)\) for the number of workers, estimates cost/time **before** large cloud runs, runs configurable grids of jobs, then **verifies** predicted vs actual wall-clock and cost.

## Paper alignment

- **Title (working / paper):** *Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics*
- **Authors (as cited in-repo):** Didachos, Georgiou, Fousteris, Kanavos
- **Core claim:** Distributed descriptor pipelines exhibit predictable scaling in **dataset size** \(D\) and **node count** \(N\); a low-order polynomial model supports **budget-aware** choice of \(N\) and validation against real Batch timings.

## Mathematical object (what “the model” means)

- **Runtime model:** \(T(N,D) = a + bN + cD + dN^2 + eND\) (seconds), with interpretable roles: baseline overhead, linear benefit of nodes, linear cost in data size, parallelism penalty (\(N^2\)), and interaction \(N \times D\).
- **Analytical optimum (interior critical point):** \(N^*(D) = -(b + eD)/(2d)\), then clamped to feasible \([N_{\min}, N_{\max}]\). Implementation: `ModelCoefficients.optimal_nodes` in `src/core/model.py`.
- **Fitting:** Coefficients are refit from experiment JSON via OLS (`fit_model`); defaults in code are **paper-style starting estimates**, not sacred constants.

## What the *software* does (research engineering, not chemistry theory)

1. **Datasets:** Synthetic/realistic SMILES CSVs by size grid (e.g. 5k–50k) and **complexity** (avg SMILES length: low / medium / high) — `datasets/generators/smiles_generator.py`.
2. **Pre-run estimator:** Given a YAML grid of \((D, N)\) and AWS pricing assumptions, outputs expected time and USD **before** submitting Batch — `experiments/estimator/experiment_estimator.py`.
3. **Execution:** Local mode for dev; AWS Batch for scale (including array/multi-shard paths for EC2 queues) — `experiments/run_experiment.py`. Modes include **`compute_only`** vs **`full_pipeline`** so comparisons match the right phase of the estimator.
4. **Verification:** After a run, MAE / RMSE / MAPE (time or cost) between estimate and actual — `experiments/verify_estimate_vs_actual.py` (supports `--run-dir`, globs, `--from-config`).
5. **Optional monitoring:** Google Sheets append for experiment telemetry (`src/monitoring/sheets.py`); infra notes in `docs/options.md`.

## Experimental discipline (what reviewers / agents should respect)

- **Never** launch full paper grids without running the **estimator** first and reading the saved `estimate_*.json`.
- Paper-style replication configs live under `experiments/configs/` (e.g. `paper_replication_*_compute_only.yaml`, `*_full_pipeline.yaml`, email pilot subsets).
- Each orchestrated run folder may contain frozen `config.yaml`, `estimation/estimate.json`, and batch/local result JSON for auditability.

## Key file map (minimal)

| Area | Path |
|------|------|
| Model + fit + optimal table | `src/core/model.py` |
| Run local / Batch from CLI or YAML | `experiments/run_experiment.py` |
| Cost/time preflight | `experiments/estimator/experiment_estimator.py` |
| Estimate vs actual metrics | `experiments/verify_estimate_vs_actual.py` |
| Human runbook | `docs/PLAN.md` |
| Step-by-step analytical checklist | `docs/ANALYTICAL_STEPS.md` |

## Vocabulary for prompts

- **\(D\)** = number of compounds (rows) in the SMILES dataset for that job.
- **\(N\)** = parallel workers / node configuration as encoded in the experiment YAML (Batch semantics: EC2 array jobs vs Fargate differ — see `docs/options.md`).
- **Replication** = same \((D,N)\) grid and complexity as a named YAML config, comparable estimates and actuals.

## What this repo is *not*

- Not a general-purpose QSAR or docking stack; the **chemistry workload** is abstracted as descriptor computation with measurable pipeline phases.
- Not guaranteed to ship production drug-design software; it is a **research + measurement harness** for cloud scheduling claims tied to the paper.

---

*Generated for quick context injection (“Claude Fast”). For full commands and credentials setup, use `README.md` and `docs/PLAN.md`.*
