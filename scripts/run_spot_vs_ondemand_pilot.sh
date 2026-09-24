#!/usr/bin/env bash
# Minimal causality pilot: D=5000 N=25 × 3 replicas on Spot, then On-Demand, same session.
# ~6 Batch jobs total (not the 24-job failure rerun).
#
# Prereqs (.env):
#   BATCH_QUEUE_SPOT=<spot queue>      e.g. chemo-ec2-queue
#   BATCH_QUEUE_ONDEMAND=<on-demand queue>
#
# After both complete:
#   PYTHONPATH=. python scripts/compare_spot_vs_ondemand_init.py
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/pilot_spot_vs_ondemand_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
export BATCH_RESULT_NOTES="pilot_spot_vs_ondemand"

exec > >(tee -a "$LOG") 2>&1

echo "=== SPOT vs ON-DEMAND PILOT D=5000 N=25 $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

for var in BATCH_QUEUE_SPOT BATCH_QUEUE_ONDEMAND; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var must be set in .env before running this pilot."
    exit 1
  fi
done

python scripts/validate_setup.py

echo ""
echo "--- Spot: 3 replicas ---"
python experiments/run_experiment.py \
  --config experiments/configs/pilot_spot_D5000_N25_rep3.yaml \
  --skip-pre-estimate --skip-verification

echo ""
echo "--- On-Demand: 3 replicas (back-to-back) ---"
python experiments/run_experiment.py \
  --config experiments/configs/pilot_ondemand_D5000_N25_rep3.yaml \
  --skip-pre-estimate --skip-verification

echo ""
echo "--- Analysis ---"
python scripts/compare_spot_vs_ondemand_init.py

echo "=== PILOT DONE log=$LOG ==="
