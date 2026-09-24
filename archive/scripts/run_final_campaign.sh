#!/usr/bin/env bash
# Launch final campaign waves. Usage:
#   ./scripts/run_final_campaign.sh 1          # wave 1 only
#   ./scripts/run_final_campaign.sh 1 3 8      # selected waves
#   ./scripts/run_final_campaign.sh all        # all waves sequentially
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy from .env.example" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .env
export PYTHONPATH=.
export SKIP_PRE_RUN_ESTIMATE=1
export BATCH_RUNNING_DEADLINE_SEC="${BATCH_RUNNING_DEADLINE_SEC:-900}"

PY="${PY:-/opt/anaconda3/envs/venv_chemoinformatics/bin/python}"
CFG_DIR="$REPO/experiments/configs/final"
LOGROOT="$REPO/tmp/final_campaign"
mkdir -p "$LOGROOT"

wave_configs() {
  local w="$1"
  case "$w" in
    1) echo final_w1_d5k_n128_od_low final_w1_d5k_n128_od_medium final_w1_d10k_n128_od_medium ;;
    2) echo final_w2_d10k_pow2_spot_low ;;
    3) echo final_w3_d50k_pow2_spot_low final_w3_d50k_pow2_spot_medium ;;
    4) echo final_w4_d20k_pow2_spot_low_rep2 final_w4_d20k_pow2_spot_medium_rep2 \
              final_w4_d40k_pow2_spot_low_rep2 final_w4_d40k_pow2_spot_medium_rep2 ;;
    5) echo final_w5_d5k_pow2_spot_high final_w5_d20k_pow2_spot_high final_w5_d40k_pow2_spot_high ;;
    6) echo final_w6_d100k_pow2_spot_low final_w6_d100k_pow2_spot_medium ;;
    7) echo final_w7_d100k_pow2_od_low final_w7_d100k_pow2_od_medium ;;
    8) echo final_w8_d20k_midn_spot_low final_w8_d20k_midn_spot_medium \
              final_w8_d40k_midn_spot_low final_w8_d40k_midn_spot_medium ;;
    9) echo final_w9_d5k_n150_185_spot_low final_w9_d5k_n150_185_spot_medium ;;
    *) echo "Unknown wave: $w" >&2; return 1 ;;
  esac
}

wave_env() {
  local w="$1"
  unset BATCH_RETRY_ATTEMPTS
  if [[ "$w" == "9" ]]; then
    export BATCH_RETRY_ATTEMPTS=4
  fi
}

wave_prereq() {
  local w="$1"
  case "$w" in
    1)
      echo "[wave 1] Ensure CE maxvCpus≥1024: python scripts/bump_ce_max_vcpus.py --max-vcpus 1024"
      ;;
    5)
      for f in smiles_5000_high.csv smiles_20000_high.csv smiles_40000_high.csv; do
        [[ -f "datasets/samples/$f" ]] || { echo "Missing datasets/samples/$f — run generate_final_campaign_datasets.sh" >&2; return 1; }
      done
      ;;
    6|7)
      for f in smiles_100000_low.csv smiles_100000_medium.csv; do
        [[ -f "datasets/samples/$f" ]] || { echo "Missing datasets/samples/$f — run generate_final_campaign_datasets.sh" >&2; return 1; }
      done
      ;;
  esac
}

run_one() {
  local base="$1"
  local wave="$2"
  local log="$LOGROOT/w${wave}_${base}.log"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] LAUNCH w${wave} $base → $log" >&2
  (
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START $base (wave $wave)"
    "$PY" experiments/run_experiment.py --config "$CFG_DIR/${base}.yaml"
    ec=$?
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DONE $base exit=$ec"
    exit $ec
  ) >"$log" 2>&1 &
  echo $!
}

run_wave() {
  local w="$1"
  local parallel="${2:-true}"
  wave_prereq "$w" || return 1
  wave_env "$w"
  local logdir="$LOGROOT/wave_${w}"
  mkdir -p "$logdir"
  local master="$logdir/master.log"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === WAVE $w START (parallel=$parallel) ===" | tee -a "$master"

  local -a configs=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && configs+=("$line")
  done < <(wave_configs "$w" | tr ' ' '\n')
  local pids=()
  for base in "${configs[@]}"; do
    if [[ ! -f "$CFG_DIR/${base}.yaml" ]]; then
      echo "Missing $CFG_DIR/${base}.yaml — run generate_final_campaign_configs.py" >&2
      return 1
    fi
    if [[ "$parallel" == "true" && ${#configs[@]} -gt 1 ]]; then
      pid="$(run_one "$base" "$w")"
      pids+=("$pid")
      sleep 8
    else
      local log="$LOGROOT/w${w}_${base}.log"
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] RUN sequential $base" | tee -a "$master"
      "$PY" experiments/run_experiment.py --config "$CFG_DIR/${base}.yaml" >"$log" 2>&1
    fi
  done

  local fail=0
  for pid in "${pids[@]:-}"; do
    if wait "$pid"; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] OK pid=$pid" | tee -a "$master"
    else
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FAIL pid=$pid" | tee -a "$master"
      fail=1
    fi
  done

  if [[ $fail -eq 0 ]]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === WAVE $w DONE OK ===" | tee -a "$master"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] === WAVE $w DONE WITH FAILURES ===" | tee -a "$master"
    return 1
  fi
}

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <wave-id>|all [wave-id ...]" >&2
  echo "Waves: 1=N128 OD gap  2=D10k low  3=D50k  4=+2rep 20/40k  5=high tier" >&2
  echo "       6=D100k Spot  7=D100k OD  8=mid-N  9=N150/185 boundary" >&2
  exit 1
fi

# Ensure configs exist
if [[ ! -f "$CFG_DIR/final_w1_d5k_n128_od_low.yaml" ]]; then
  "$PY" scripts/generate_final_campaign_configs.py
fi

waves=()
if [[ "$1" == "all" ]]; then
  waves=(1 2 3 4 5 6 7 8 9)
else
  waves=("$@")
fi

overall_fail=0
for w in "${waves[@]}"; do
  if ! run_wave "$w" true; then
    overall_fail=1
  fi
done

exit "$overall_fail"
