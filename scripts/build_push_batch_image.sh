#!/usr/bin/env bash
# Build and push the RDKit Batch worker image to ECR, then register a new job definition revision.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-central-1}}"
REPO_NAME="${ECR_REPO_NAME:-cheminformatics-descriptor-worker}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
JOB_DEF_NAME="${AWS_BATCH_JOB_DEFINITION:-chemo-ec2-worker}"

echo "==> Resolving AWS account..."
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "==> Ensuring ECR repository ${REPO_NAME} exists..."
aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${REGION}" >/dev/null

echo "==> Docker login to ECR (${REGION})..."
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "==> Building image from docker/Dockerfile (linux/amd64 for AWS Batch EC2)..."
docker build --platform linux/amd64 -f docker/Dockerfile -t "${REPO_NAME}:${IMAGE_TAG}" .

echo "==> Tagging and pushing ${ECR_URI}:${IMAGE_TAG}..."
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}"

echo "==> Registering Batch job definition ${JOB_DEF_NAME}..."
export BATCH_IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"
export AWS_BATCH_JOB_DEFINITION="${JOB_DEF_NAME}"
python scripts/register_batch_job_definition.py

echo "Done. Image: ${ECR_URI}:${IMAGE_TAG}"
