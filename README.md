# Performance and Cost Benchmarking of Cloud Resources for Large-Scale Molecular Descriptor Computation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Venue](https://img.shields.io/badge/venue-forthcoming-lightgrey.svg)](#)
[![DOI](https://img.shields.io/badge/DOI-forthcoming-lightgrey.svg)](#)

Companion source code for the paper of the same title.  
**Paper PDF / publisher DOI:** forthcoming.

**Authors:** Christos Didachos, Dimitrios Georgiou, Manolis Fousteris, Andreas Kanavos  
**Affiliations:** University of Patras / Ionian University

---

## Abstract

Large-scale molecular descriptor computation is a common bottleneck in cheminformatics pipelines. This companion repository provides an AWS Batch measurement harness and analysis tooling to benchmark **wall-clock performance** and **monetary cost** across dataset size \(D\), worker count \(N\), SMILES complexity, and Spot vs On-Demand capacity — supporting reproducible cloud-resource decisions for descriptor workloads.

---

## Contributions

- End-to-end **AWS Batch** experiment runner (local dry-run + EC2 array jobs)
- Pre-run **time/cost estimator** aligned with the paper performance model
- Timing decomposition (upload, cluster init, parallel compute, pipeline totals)
- Optional Google Sheets sync for multi-replicate campaign tracking
- Analysis scripts for cost backfill, model fits (N≤185), and config selection

---

## Method / pipeline

```text
SMILES CSV  →  S3 shards  →  AWS Batch workers (RDKit descriptors)
                ↓
         phase timings + cost
                ↓
     Sheets / JSON results  →  model fit & cost analysis
```

Resource-allocation model used in the study:

\[
T(N,D) = a + bN + cD + dN^{2} + eND, \qquad
N^{*}(D) = -\frac{b + eD}{2d}\quad (d > 0)
\]

Canonical implementation: `src/descriptor_cloud_benchmark/core/model.py`.

---

## This system is / is not

| Is | Is not |
|----|--------|
| A **benchmark harness** for descriptor jobs on AWS Batch | A production cheminformatics SaaS |
| A way to compare **Spot vs On-Demand** cost/time | A guarantee of lowest cloud prices in every region |
| Code to reproduce experimental grids and analyses | A substitute for the paper’s full empirical narrative |

---

## Repository layout

```text
README.md, LICENSE, NOTICE, CITATION.cff, pyproject.toml
main.py                              # thin CLI
config/config.example.ini            # placeholders only
src/descriptor_cloud_benchmark/     # installable package
  core/   aws/   worker/   monitoring/
experiments/                         # runner, estimator, example configs
scripts/                             # paper analysis helpers + run.sh
datasets/generators/                 # SMILES generators
docker/                              # Batch worker image
tests/
data/                                # paper coefficient JSON snapshots
outputs/                             # local artifacts (gitignored contents)
archive/                             # historical ops configs (optional)
```

---

## Quick start

```bash
conda env create -f environment.yml
conda activate venv_chemoinformatics
pip install -e ".[dev]"
cp .env.example .env          # AWS / S3 / Batch / optional Sheets
# or: cp config/config.example.ini config/config.ini
```

```bash
# Model probe
python main.py model --N 50 --D 10000
# → T(N,D) seconds and N*(D)

# Pre-run estimate (before spending AWS budget)
python main.py estimate \
  --config experiments/configs/examples/experiment_00_quick.yaml \
  --dataset-dir datasets/samples

# Local dry-run
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/examples/experiment_mock_100.yaml \
  --local

# Tests
pytest -q
```

Generate SMILES samples with `datasets/generators/` (large CSVs are not shipped).

Authenticate with `aws configure` or keys in `.env`. Never commit secrets.

---

## Ethics & safety

- No human-subjects or clinical data are used in this repository.
- Do not commit AWS keys, OAuth tokens, or service-account JSON.
- Reported USD costs are study- and account-specific.

---

## Authors

- **Christos Didachos** — University of Patras / Ionian University  
- **Dimitrios Georgiou** — University of Patras / Ionian University  
- **Manolis Fousteris** — University of Patras / Ionian University  
- **Andreas Kanavos** — University of Patras / Ionian University  

---

## Acknowledgments

AWS Batch / Spot capacity and institutional research computing support as acknowledged in the paper (forthcoming).

---

## How to cite

If you use this software or method, please cite:

```bibtex
@inproceedings{didachos2025descriptorbenchmark,
  title     = {Performance and Cost Benchmarking of Cloud Resources for Large-Scale Molecular Descriptor Computation},
  author    = {Didachos, Christos and Georgiou, Dimitrios and Fousteris, Manolis and Kanavos, Andreas},
  year      = {2025},
  note      = {Publisher DOI forthcoming; code: https://github.com/dimigeorgiou/molecular-descriptor-cloud-benchmark}
}
```

**APA:**  
Didachos, C., Georgiou, D., Fousteris, M., & Kanavos, A. (2025). *Performance and Cost Benchmarking of Cloud Resources for Large-Scale Molecular Descriptor Computation*. Publisher DOI forthcoming. Companion code: https://github.com/dimigeorgiou/molecular-descriptor-cloud-benchmark

---

## License

MIT — see `LICENSE`. Scope limits — see `NOTICE`.
