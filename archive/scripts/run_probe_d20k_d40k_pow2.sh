#!/usr/bin/env bash
# D=20k & D=40k pow2 low-N sweep — low then medium, 1 replica each.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
source .env
export PYTHONPATH=.
export SKIP_PRE_RUN_ESTIMATE=1
export BATCH_RUNNING_DEADLINE_SEC=900

LOG="$REPO/tmp/probe_d20k_d40k_pow2_sweep.log"
PY="/opt/anaconda3/envs/venv_chemoinformatics/bin/python"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START D=20k/40k pow2 low+medium (1 rep)" | tee -a "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === probe_d20k_d40k_pow2_spot_low (10 cells) ===" | tee -a "$LOG"
"$PY" experiments/run_experiment.py \
  --config experiments/configs/probe_d20k_d40k_pow2_spot_low.yaml \
  2>&1 | tee -a "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === probe_d20k_d40k_pow2_spot_medium (10 cells) ===" | tee -a "$LOG"
"$PY" experiments/run_experiment.py \
  --config experiments/configs/probe_d20k_d40k_pow2_spot_medium.yaml \
  2>&1 | tee -a "$LOG"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE D=20k/40k pow2 sweep" | tee -a "$LOG"
