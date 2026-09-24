#!/usr/bin/env bash
# Validation gate: 4 cells × 10 On-Demand replicas (40 batch array runs).
# Prereq: chemo-ec2-worker-ondemand has minScaleDownDelayMinutes=20
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/validation_rep10_ondemand_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.

if [[ -t 1 ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >>"$LOG" 2>&1
fi

echo "=== VALIDATION GATE (4×10 On-Demand replicas) $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

CONFIGS=(
  experiments/configs/validation_low_D5000_N25_rep10_ondemand.yaml
  experiments/configs/validation_low_D5000_N50_rep10_ondemand.yaml
  experiments/configs/validation_medium_D5000_N25_rep10_ondemand.yaml
  experiments/configs/validation_medium_D5000_N50_rep10_ondemand.yaml
)

python scripts/validate_setup.py

for cfg in "${CONFIGS[@]}"; do
  echo ""
  echo ">>> Running $cfg"
  python experiments/run_experiment.py --config "$cfg" --skip-pre-estimate --skip-verification
done

echo ""
echo "--- Analysis ---"
python scripts/analyze_validation_rep10.py --out tmp/validation_rep10_report.json
python scripts/project_full_pipeline_cost.py \
  --validation-report tmp/validation_rep10_report.json \
  --out tmp/full_pipeline_cost_projection.json

echo "=== DONE log=$LOG ==="
