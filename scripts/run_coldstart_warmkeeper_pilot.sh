#!/usr/bin/env bash
# Warm-keeper rerun: 10 sequential N=25 replicas after CE scale-down delay = 20 min.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/coldstart_warmkeeper_pilot_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
export BATCH_RESULT_NOTES="${BATCH_RESULT_NOTES:-coldstart_warmkeeper_pilot}"

if [[ -t 1 ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >>"$LOG" 2>&1
fi

echo "=== WARM-KEEPER PILOT (On-Demand, scale-down 20m, 10 replicas) $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

python scripts/validate_setup.py

python experiments/run_experiment.py \
  --config experiments/configs/pilot_coldstart_warmkeeper_ondemand_rep10.yaml \
  --skip-pre-estimate --skip-verification

echo ""
echo "--- Analysis ---"
python scripts/analyze_coldstart_decay.py \
  --experiment-id pilot_coldstart_warmkeeper_ondemand_rep10 \
  --out tmp/coldstart_warmkeeper_report.json

echo "=== DONE log=$LOG ==="
