#!/usr/bin/env bash
# Resume unfinished rep3 pow2 Spot grids (residual N only).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
source .env
export PYTHONPATH=.
export SKIP_PRE_RUN_ESTIMATE=1
export BATCH_RUNNING_DEADLINE_SEC=900

PY="/opt/anaconda3/envs/venv_chemoinformatics/bin/python"
LOGDIR="$REPO/tmp/rep3_pow2_resume"
mkdir -p "$LOGDIR"
MASTER="$LOGDIR/master.log"

CONFIGS=(
  experiments/configs/rep3_d5k_pow2_spot_low_resume.yaml
  experiments/configs/rep3_d5k_pow2_spot_medium_resume.yaml
  experiments/configs/rep3_d10k_pow2_spot_medium_resume.yaml
  experiments/configs/rep3_d20k_pow2_spot_low_resume.yaml
  experiments/configs/rep3_d20k_pow2_spot_medium_resume.yaml
  experiments/configs/rep3_d40k_pow2_spot_low_resume.yaml
  experiments/configs/rep3_d40k_pow2_spot_medium_resume.yaml
)

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START resume parallel rep3 pow2 — ${#CONFIGS[@]} jobs" | tee -a "$MASTER"

PIDS=()
for cfg in "${CONFIGS[@]}"; do
  base="$(basename "$cfg" .yaml)"
  log="$LOGDIR/${base}.log"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] LAUNCH $base → $log" | tee -a "$MASTER"
  (
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START $base"
    "$PY" experiments/run_experiment.py --config "$cfg"
    ec=$?
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE $base exit=$ec"
    exit $ec
  ) >"$log" 2>&1 &
  PIDS+=("$!")
  sleep 8
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] PIDs: ${PIDS[*]}" | tee -a "$MASTER"
echo "${PIDS[*]}" > "$LOGDIR/pids.txt"

fail=0
for i in "${!PIDS[@]}"; do
  pid="${PIDS[$i]}"
  cfg="${CONFIGS[$i]}"
  base="$(basename "$cfg" .yaml)"
  if wait "$pid"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] OK $base (pid=$pid)" | tee -a "$MASTER"
  else
    ec=$?
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FAIL $base (pid=$pid exit=$ec)" | tee -a "$MASTER"
    fail=1
  fi
done

if [[ $fail -eq 0 ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ALL DONE OK" | tee -a "$MASTER"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ALL DONE WITH FAILURES" | tee -a "$MASTER"
  exit 1
fi
