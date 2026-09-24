#!/usr/bin/env bash
# Rerun the 8 shared failed (D,N) cells (4 pairs × low/medium) on On-Demand with n_replicas=3.
# Uses NEW experiment_id so Sheets upsert does not collide with Spot replication rows.
#
# Prereqs in .env:
#   BATCH_QUEUE_ONDEMAND=<your on-demand queue ARN or name>
#   BATCH_QUEUE_SPOT=<spot queue>  (optional; not used when use_spot=false)
#   AWS_BATCH_JOB_DEFINITION, S3_BUCKET, GOOGLE_SHEETS_ID, AWS credentials
#
# Jobs: 4 (D,N) × 3 replicas × 2 complexities = 24 Batch array submissions.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/rerun_failed_8_ondemand_rep3_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
export BATCH_RESULT_NOTES="ondemand_rep3_rerun"
export SHEETS_UPDATE_COMPLEXITY=0

exec > >(tee -a "$LOG") 2>&1

echo "=== RERUN 8 FAILED CELLS (On-Demand, n_replicas=3) $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

if [[ -z "${BATCH_QUEUE_ONDEMAND:-}" ]]; then
  echo "WARN: BATCH_QUEUE_ONDEMAND unset — resolve_batch_queue will fall back to legacy AWS_BATCH_JOB_QUEUE"
fi

python scripts/validate_setup.py

for cfg in \
  experiments/configs/rerun_failed_8_low_ondemand_rep3.yaml \
  experiments/configs/rerun_failed_8_medium_ondemand_rep3.yaml
do
  echo ""
  echo "--- Config: $cfg ---"
  python experiments/run_experiment.py \
    --config "$cfg" \
    --skip-pre-estimate \
    --skip-verification
done

echo ""
echo "=== Updating Sheets pivot formulas ==="
python scripts/update_sheets_formulas.py

echo ""
echo "=== Metric analysis ==="
python scripts/analyze_paper_metrics.py

echo "=== RERUN DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) log=$LOG ==="
