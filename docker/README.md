# Batch worker container (Phase 0)

Real RDKit descriptor computation for AWS Batch array shards.

## Prerequisites

- Docker Desktop running (`docker info` must succeed)
- AWS CLI configured (same credentials as `.env`)
- Region: `eu-central-1` (or set `AWS_REGION`)

## Build, push, register job definition

```bash
conda activate venv_chemoinformatics
export PYTHONPATH=.
set -a && source .env && set +a

bash scripts/build_push_batch_image.sh
```

This will:

1. Create ECR repo `cheminformatics-descriptor-worker` if missing
2. Build `docker/Dockerfile` (conda-forge RDKit + pip deps)
3. Push to ECR
4. Register a new revision of `AWS_BATCH_JOB_DEFINITION` (default: `chemo-ec2-worker`)

**Important:** The previous job definition used `amazonlinux:latest` with `echo hello world` (~1s jobs). After this script, Batch runs `python -m src.worker.batch_shard_worker`.

## Smoke test after deploy

```bash
PYTHONPATH=. python experiments/run_experiment.py \
  --config experiments/configs/smoke_batch_verify.yaml \
  --dataset-dir datasets/samples
```

Expect `computation_sec` for D=5000 around **4–10s** per shard (N=10 → ~500 mols/shard), not ~1s.

## Local docker smoke (no AWS)

```bash
docker build -f docker/Dockerfile -t chemo-worker:test .
docker run --rm \
  -e DATASET_S3_BUCKET=... -e DATASET_S3_PREFIX=... \
  chemo-worker:test
```

(S3 env vars required unless you mount a local CSV and patch the worker for dev.)
