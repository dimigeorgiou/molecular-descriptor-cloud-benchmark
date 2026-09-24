# 🤖 AGENTS.md — Cursor Pro Agent Configuration
# Optimal Resource Allocation for Distributed Descriptor Computation

## Project Mission
This project implements and extends the research paper:
**"Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics"**
by Didachos, Georgiou, Fousteris, Kanavos.

The core goal: **predict the optimal number of AWS Batch compute nodes** to minimize execution
time and cost for molecular descriptor computation (SMILES → descriptors), using the fitted
regression model T(N,D) = a + bN + cD + dN² + eND.

---

## Agent Rules

### 1. Always Read Context First
Before writing any code, read:
- `docs/PLAN.md` for the research runbook (estimate → run → verify)
- `SKILLS.md` for patterns and utilities
- `experiments/configs/` for experiment definitions
- `src/core/model.py` for the performance model

### 2. Code Style
- Python 3.10+, type hints everywhere
- Use `loguru` for logging, never `print()` in production code
- All AWS calls must use `boto3` with proper error handling and retries
- Environment variables via `python-dotenv` (.env file, never hardcode credentials)
- Dataclasses or Pydantic models for all data structures
- Every function must have a docstring

### 3. Experiment Discipline
- **Never run full experiments without first running `experiment_estimator.py`**
- All experiment configs live in `experiments/configs/*.yaml`
- Results always written to `experiments/results/` with timestamps
- Google Sheets sync is automatic after each experiment completes

### 4. AWS Batch Rules
- Job definitions live in `aws/job_definitions/`
- Use Spot Instances by default (80% cost savings) with On-Demand fallback
- Always tag AWS resources: `Project=cheminformatics-descriptors`, `Environment=research`
- Compute environment: minimum 0 vCPUs (scale to zero when idle)
- Preferred instance types: `c5.2xlarge`, `c5.4xlarge`, `c5.9xlarge` (compute optimized)

### 5. Dataset Generation
- All datasets generated via `datasets/generators/smiles_generator.py`
- Use realistic SMILES with configurable average length (default: 57 chars per paper)
- Complexity levels: `low` (avg 30 chars), `medium` (avg 57 chars), `high` (avg 90 chars)
- Sizes tested in paper: 5k, 10k, 20k, 30k, 40k, 50k compounds

### 6. Monitoring
- All metrics → Google Sheets (real-time via Sheets API)
- Local dashboard via `monitoring/dashboard.py` (Rich TUI)
- CloudWatch metrics auto-collected for each Batch job

### 7. The Performance Model
```
T(N, D) = a + bN + cD + dN² + eND

Optimal nodes: N*(D) = -(b + eD) / (2d)

Fitted coefficients (from paper's experimental data):
a ≈ 500.0   (baseline overhead)
b ≈ -8.0    (linear node benefit)
c ≈ 0.008   (data size cost)
d ≈ 0.05    (quadratic overhead from parallelism)
e ≈ 0.00002 (interaction term)

These are initial estimates — the experiment re-fits them from real data.
```

---

## File Ownership (don't touch without reason)
| File | Owner | Purpose |
|------|-------|---------|
| `src/core/model.py` | core | Performance model + optimizer |
| `src/aws/batch_manager.py` | aws | AWS Batch job management |
| `src/monitoring/sheets.py` | monitoring | Google Sheets integration |
| `experiments/configs/*.yaml` | experiments | Experiment definitions |
| `.env` | secrets | Credentials (never commit) |

---

## When Agent Gets Stuck
1. Check `logs/` for error details
2. Run `python scripts/validate_setup.py` to verify AWS + GSheets connectivity
3. Check `experiments/results/` for partial results
4. Re-read `PLAN.md` for current task context
