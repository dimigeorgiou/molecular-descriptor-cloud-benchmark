# Performance and Cost Benchmarking of Cloud Resources for Large-Scale Molecular Descriptor Computation

Code accompanying the paper of the same title: empirical **performance and cost benchmarking** of cloud resources for large-scale molecular descriptor computation on **AWS Batch**.

Paper model (resource-allocation analysis):

\[
T(N,D) = a + bN + cD + dN^{2} + eND, \qquad
N^{*}(D) = -\frac{b + eD}{2d}\quad (d > 0)
\]

where \(N\) is the worker count and \(D\) is the dataset size (number of molecules).

**Authors:** Christos Didachos, Dimitrios Georgiou, Manolis Fousteris, Andreas Kanavos  
**Affiliations:** University of Patras / Ionian University

---

## Repository layout

```
src/                 # Core library (model, Batch timing, workers, Sheets)
experiments/         # Runner, estimator, example + paper2 configs
scripts/             # Paper analysis / setup helpers
datasets/generators/ # SMILES dataset generators
docker/              # Batch worker image
tests/               # Unit tests
data/                # Paper coefficient / table JSON snapshots
docs/                # Paper PDF + AWS Batch options note
archive/             # Historical ops scripts & campaign configs (not required to reproduce)
```

---

## Setup

```bash
conda env create -f environment.yml
conda activate venv_chemoinformatics
cd /path/to/molecular-descriptor-cloud-benchmark
export PYTHONPATH=.
cp .env.example .env   # fill AWS / S3 / Batch / optional Sheets
```

Pip-only core (RDKit still via conda):

```bash
pip install -r requirements.txt
pip install -r requirements-analysis.txt   # optional plotting
conda install -c conda-forge rdkit
```

Authenticate with `aws configure` **or** keys in `.env`. Never commit `.env` or service-account JSON.

```bash
aws sts get-caller-identity
PYTHONPATH=. python scripts/validate_setup.py
```

---

## Quick start

**1. Generate a small SMILES set**

```bash
PYTHONPATH=. python datasets/generators/smiles_generator.py \
  --n-compounds 100 --complexity low --output datasets/samples/smiles_100_low.csv
```

**2. Estimate time/cost before spending AWS budget**

```bash
PYTHONPATH=. python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/examples/experiment_00_quick.yaml \
  --dataset-dir datasets/samples
```

**3. Local dry-run**

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/examples/experiment_mock_100.yaml \
  --local
```

**4. Paper-scale Batch** (requires configured queue + job definition in `.env`)

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/examples/paper_replication_low_full_pipeline.yaml
```

**5. Tests**

```bash
PYTHONPATH=. pytest -q
```

---

## Performance model API

```bash
PYTHONPATH=. python -c "
from src.core.model import ModelCoefficients
m = ModelCoefficients()
print(m.predict(N=50, D=10000))
print(m.optimal_nodes(D=10000))
"
```

Canonical implementation: `src/core/model.py`.

---

## Paper analysis scripts

| Script | Role |
|--------|------|
| `scripts/paper2_task1_task2_audit.py` | Sheet audit + Spot cost backfill |
| `scripts/run_paper2_core_topup.py` | Top-up replicates on established grid |
| `scripts/paper2_tasks3_5_n185.py` | Time/cost models + config selector (N≤185) |
| `scripts/paper2_task3_refit_raw_rows.py` | Raw-row refit / medians check |
| `scripts/analyze_paper_metrics.py` | Metric diagnostics |

---

## How to cite

If you use this code or the associated results, please cite:

```bibtex
@inproceedings{didachos2025descriptorbenchmark,
  title={Performance and Cost Benchmarking of Cloud Resources for Large-Scale Molecular Descriptor Computation},
  author={Didachos, Christos and Georgiou, Dimitrios and Fousteris, Manolis and Kanavos, Andreas},
  year={2025}
}
```

**APA-style:**  
Didachos, C., Georgiou, D., Fousteris, M., & Kanavos, A. (2025). *Performance and Cost Benchmarking of Cloud Resources for Large-Scale Molecular Descriptor Computation*.

**Code:** https://github.com/dimigeorgiou/molecular-descriptor-cloud-benchmark

---

## License / secrets

Research code accompanying the paper. Do not commit credentials; rotate any key that was ever shared outside a secret store.
