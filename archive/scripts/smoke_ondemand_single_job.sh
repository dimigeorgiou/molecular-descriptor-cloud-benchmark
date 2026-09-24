#!/usr/bin/env bash
# Throwaway non-array single-node job on On-Demand queue (console-equivalent smoke).
# AWS Batch array jobs require size > 1; this uses submit-job without arrayProperties.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a

QUEUE="${BATCH_QUEUE_ONDEMAND:-chemo-ec2-ondemand-queue}"
JOB_DEF="${AWS_BATCH_JOB_DEFINITION:-chemo-ec2-worker}"
BUCKET="${S3_BUCKET:-${AWS_S3_BUCKET:?Set S3 bucket in .env}}"
REGION="${AWS_REGION:-eu-central-1}"
PREFIX="chemoinformatics/smoke_ondemand_$(date +%Y%m%d_%H%M%S)"
JOB_NAME="smoke-ondemand-single-$(date +%H%M%S)"
OVERRIDES_FILE="/tmp/smoke_ondemand_overrides_$$.json"

echo "Queue: $QUEUE"
echo "Job definition: $JOB_DEF"
echo "S3 prefix: s3://$BUCKET/$PREFIX"
export BUCKET PREFIX REGION

python - <<PY
import os, subprocess
from pathlib import Path
src = Path("datasets/samples/smiles_5000_low.csv")
dst = Path("/tmp/smoke_shard_0.csv")
lines = src.read_text().splitlines()
Path(dst).write_text("\n".join(lines[:101]) + "\n")
bucket = os.environ["BUCKET"]
prefix = os.environ["PREFIX"]
region = os.environ["REGION"]
subprocess.check_call([
    "aws", "s3", "cp", str(dst),
    f"s3://{bucket}/{prefix}/shard_0.csv",
    "--region", region,
])
print("Uploaded shard_0.csv")
PY

python - <<PY > "$OVERRIDES_FILE"
import json, os
print(json.dumps({
  "environment": [
    {"name": "DATASET_S3_BUCKET", "value": os.environ["BUCKET"]},
    {"name": "DATASET_S3_PREFIX", "value": os.environ["PREFIX"]},
    {"name": "DATASET_SIZE", "value": "5000"},
    {"name": "N_NODES", "value": "1"},
    {"name": "SMILES_COMPLEXITY", "value": "low"},
    {"name": "DESCRIPTOR_METHOD", "value": "default"},
  ]
}))
PY

JOB_ID=$(aws batch submit-job \
  --job-name "$JOB_NAME" \
  --job-queue "$QUEUE" \
  --job-definition "$JOB_DEF" \
  --share-identifier "${BATCH_SHARE_IDENTIFIER:-default}" \
  --region "$REGION" \
  --container-overrides "file://$OVERRIDES_FILE" \
  --query jobId --output text)
rm -f "$OVERRIDES_FILE"

echo "Submitted job $JOB_NAME id=$JOB_ID"
echo "Polling until terminal state..."

for i in $(seq 1 120); do
  STATUS=$(aws batch describe-jobs --jobs "$JOB_ID" --region "$REGION" \
    --query 'jobs[0].status' --output text)
  REASON=$(aws batch describe-jobs --jobs "$JOB_ID" --region "$REGION" \
    --query 'jobs[0].statusReason' --output text 2>/dev/null || true)
  echo "  [$i] status=$STATUS ${REASON:+reason=$REASON}"
  case "$STATUS" in
    SUCCEEDED)
      echo "SMOKE OK: On-Demand queue accepts jobs and worker SUCCEEDED."
      exit 0
      ;;
    FAILED)
      echo "SMOKE FAILED — check Batch console for job $JOB_ID"
      exit 1
      ;;
  esac
  sleep 15
done
echo "Timed out waiting for job $JOB_ID"
exit 2
