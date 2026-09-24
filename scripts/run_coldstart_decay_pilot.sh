#!/usr/bin/env bash
# Cold-start decay pilot: 10 sequential N=25 replicas on On-Demand (one session).
# Spot vs On-Demand is NOT tested — pricing tier is dead variable.
#
# Prereq: BATCH_QUEUE_ONDEMAND=chemo-ec2-ondemand-queue in .env
# Optional warm-keeper rerun: set scale-in delay on chemo-ec2-worker-ondemand CE
#   (Console → Compute environments → chemo-ec2-worker-ondemand → Edit →
#    Scale down delay 15-20 min) then re-run this script.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/coldstart_decay_pilot_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
export BATCH_RESULT_NOTES="${BATCH_RESULT_NOTES:-coldstart_decay_pilot}"

if [[ -t 1 ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >>"$LOG" 2>&1
fi

echo "=== COLD-START DECAY PILOT (On-Demand, 10 replicas) $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

if [[ -z "${BATCH_QUEUE_ONDEMAND:-}" ]]; then
  echo "ERROR: BATCH_QUEUE_ONDEMAND must be set in .env"
  exit 1
fi

python scripts/validate_setup.py

python experiments/run_experiment.py \
  --config experiments/configs/pilot_coldstart_decay_ondemand_rep10.yaml \
  --skip-pre-estimate --skip-verification

echo ""
echo "--- Analysis ---"
python scripts/analyze_coldstart_decay.py

echo "=== DONE log=$LOG ==="
