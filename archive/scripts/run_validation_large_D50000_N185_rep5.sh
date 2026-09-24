#!/usr/bin/env bash
# Large-cell validation: D=50000, N=185 × 5 On-Demand replicas × low + medium.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/validation_large_D50000_N185_rep5_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
# Large array (185 children) may need longer wall clock per replica.
export BATCH_ARRAY_TIMEOUT_SEC="${BATCH_ARRAY_TIMEOUT_SEC:-7200}"

if [[ -t 1 ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >>"$LOG" 2>&1
fi

echo "=== LARGE CELL VALIDATION D=50000 N=185 rep5 (low+medium) $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

CONFIGS=(
  experiments/configs/validation_large_low_D50000_N185_rep5_ondemand.yaml
  experiments/configs/validation_large_medium_D50000_N185_rep5_ondemand.yaml
)

python scripts/validate_setup.py

echo ""
echo "--- Pre-run estimator snapshot ---"
for cfg in "${CONFIGS[@]}"; do
  python experiments/estimator/experiment_estimator.py --config "$cfg" --dataset-dir datasets/samples
done

for cfg in "${CONFIGS[@]}"; do
  echo ""
  echo ">>> Running $cfg"
  python experiments/run_experiment.py --config "$cfg"
done

echo ""
echo "--- Estimate vs actual ---"
python scripts/analyze_validation_large_cell.py --out tmp/validation_large_D50000_N185_report.json

echo "=== DONE log=$LOG ==="
