#!/usr/bin/env bash
# Generate SMILES CSVs required for the final campaign (high tier + D=100k).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
export PYTHONPATH=.

PY="${PY:-/opt/anaconda3/envs/venv_chemoinformatics/bin/python}"
OUT="${OUT:-datasets/samples}"
LOG="${LOG:-tmp/final_campaign_datasets.log}"
mkdir -p "$(dirname "$LOG")" "$OUT"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] dataset generation START → $LOG" | tee "$LOG"

gen() {
  local complexity="$1"
  shift
  local sizes=("$@")
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] complexity=$complexity sizes=${sizes[*]}" | tee -a "$LOG"
  "$PY" datasets/generators/smiles_generator.py \
    --sizes "${sizes[@]}" \
    --complexity "$complexity" \
    --output-dir "$OUT" \
    --seed 42 2>&1 | tee -a "$LOG"
}

# High tier (never generated before)
gen high 5000 20000 40000

# D=100k anchor (low + medium)
gen low 100000
gen medium 100000

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] dataset generation DONE" | tee -a "$LOG"
ls -lh "$OUT"/smiles_100000_*.csv "$OUT"/smiles_*_high.csv 2>/dev/null | tee -a "$LOG"
