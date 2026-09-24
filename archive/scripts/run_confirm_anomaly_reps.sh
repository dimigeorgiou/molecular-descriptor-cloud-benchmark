#!/usr/bin/env bash
# 5-rep confirmation runs for two scheduling-spike anomalies.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
source .env
export PYTHONPATH=.
export SKIP_PRE_RUN_ESTIMATE=1
export BATCH_RUNNING_DEADLINE_SEC=900

LOG="$REPO/tmp/confirm_anomaly_reps.log"
PY="/opt/anaconda3/envs/venv_chemoinformatics/bin/python"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START anomaly 5-rep confirmations" | tee -a "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === confirm_d50k_n32_spot_low (5 reps) ===" | tee -a "$LOG"
"$PY" experiments/run_experiment.py \
  --config experiments/configs/confirm_d50k_n32_spot_low.yaml \
  2>&1 | tee -a "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === confirm_d20k_n8_spot_medium (5 reps) ===" | tee -a "$LOG"
"$PY" experiments/run_experiment.py \
  --config experiments/configs/confirm_d20k_n8_spot_medium.yaml \
  2>&1 | tee -a "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE anomaly confirmations" | tee -a "$LOG"
