#!/usr/bin/env bash
# Extend D=20k/40k to N=64,128 — low then medium, 1 replica (8 cells total).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
source .env
export PYTHONPATH=.
export SKIP_PRE_RUN_ESTIMATE=1
export BATCH_RUNNING_DEADLINE_SEC=900

LOG="$REPO/tmp/probe_d20k_d40k_pow2_ext_sweep.log"
PY="/opt/anaconda3/envs/venv_chemoinformatics/bin/python"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START D=20k/40k N=64,128 ext (low+medium, 1 rep)" | tee -a "$LOG"

for cfg in low_ext medium_ext; do
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === probe_d20k_d40k_pow2_spot_${cfg} (4 cells) ===" | tee -a "$LOG"
  "$PY" experiments/run_experiment.py \
    --config "experiments/configs/probe_d20k_d40k_pow2_spot_${cfg}.yaml" \
    2>&1 | tee -a "$LOG"
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE ext sweep" | tee -a "$LOG"
