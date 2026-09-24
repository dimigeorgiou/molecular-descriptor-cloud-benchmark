#!/usr/bin/env bash
# Overnight: low + medium compute_only paper grids, fit, verify, sheets.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/overnight_paper_grid_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.

exec > >(tee -a "$LOG") 2>&1

echo "=== OVERNIGHT PAPER GRID START $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

run_grid() {
  local cfg="$1"
  local name="$2"
  echo "--- Estimator: $cfg ---"
  python experiments/estimator/experiment_estimator.py \
    --config "$cfg" --dataset-dir datasets/samples --verbose || true
  echo "--- Batch run: $cfg ---"
  python experiments/run_experiment.py --config "$cfg" --dataset-dir datasets/samples
  echo "--- Verify: $name ---"
  local run_dir
  run_dir="$(ls -dt experiments/results/${name}_* 2>/dev/null | head -1)"
  if [[ -n "$run_dir" && -d "$run_dir" ]]; then
    python experiments/verify_estimate_vs_actual.py --run-dir "$run_dir" \
      --json-out "$run_dir/verification_report.json" || true
    python - <<PY
import json
from pathlib import Path
from src.core.model import fit_model

run_dir = Path("$run_dir")
actual_files = sorted(run_dir.glob("batch_*.json"))
if not actual_files:
    raise SystemExit("no batch json in " + run_dir)
rows = json.loads(actual_files[-1].read_text())
expected = 6 * 7  # dataset_sizes × node_configs
if len(rows) < expected:
    raise SystemExit(f"refusing fit: {len(rows)}/{expected} grid points in {actual_files[-1]}")
model = fit_model(rows)
out = run_dir / "fitted_model.json"
model.save(out)
print(f"Fitted {out} R2={model.r_squared} n={len(rows)}")
PY
  fi
}

run_grid "experiments/configs/paper_replication_low_compute_only.yaml" "paper_replication_low_compute_only"

run_grid "experiments/configs/paper_replication_medium_compute_only.yaml" "paper_replication_medium_compute_only"

# One refresh after both grids: per-experiment filter would blank the other complexity tab.
python scripts/update_sheets_formulas.py || true

echo "=== OVERNIGHT PAPER GRID DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
