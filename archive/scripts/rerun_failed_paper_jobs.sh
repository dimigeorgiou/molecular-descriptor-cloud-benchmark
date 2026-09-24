#!/usr/bin/env bash
# Re-submit only (D,N) pairs that FAILED in the 2026-07-08 paper replication grids.
# Appends new rows to Google Sheets Results (pivots filter Status=SUCCEEDED).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/rerun_failed_paper_jobs_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
export BATCH_RESULT_NOTES="retry_20260708"
export SHEETS_UPDATE_COMPLEXITY=0

exec > >(tee -a "$LOG") 2>&1

echo "=== RERUN FAILED PAPER JOBS $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

run_pair() {
  local complexity="$1" name="$2" d="$3" n="$4"
  echo ""
  echo "--- ${complexity} D=${d} N=${n} ---"
  python experiments/run_experiment.py \
    --name "$name" \
    --mode compute_only \
    --smiles-complexity "$complexity" \
    --dataset-sizes "$d" \
    --node-configs "$n" \
    --dataset-dir datasets/samples \
    --skip-pre-estimate \
    --skip-verification
}

# Low complexity failures (from batch JSON status=FAILED)
run_pair low paper_replication_low_compute_only 5000 150
run_pair low paper_replication_low_compute_only 5000 185
run_pair low paper_replication_low_compute_only 10000 185
run_pair low paper_replication_low_compute_only 20000 185
run_pair low paper_replication_low_compute_only 50000 50

# Medium complexity failures
run_pair medium paper_replication_medium_compute_only 5000 150
run_pair medium paper_replication_medium_compute_only 5000 185
run_pair medium paper_replication_medium_compute_only 10000 185
run_pair medium paper_replication_medium_compute_only 20000 185
run_pair medium paper_replication_medium_compute_only 30000 100

echo ""
echo "=== Updating Sheets pivot formulas ==="
python scripts/update_sheets_formulas.py

echo ""
echo "=== Metric analysis ==="
python scripts/analyze_paper_metrics.py

echo "=== RERUN DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) log=$LOG ==="
