#!/usr/bin/env bash
# Resume after low grid completed; overnight script died on bash syntax error.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="tmp/resume_medium_grid_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tmp

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.

exec > >(tee -a "$LOG") 2>&1

echo "=== RESUME MEDIUM GRID $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

CFG="experiments/configs/paper_replication_medium_compute_only.yaml"
NAME="paper_replication_medium_compute_only"

python experiments/estimator/experiment_estimator.py \
  --config "$CFG" --dataset-dir datasets/samples --verbose || true

python experiments/run_experiment.py --config "$CFG" --dataset-dir datasets/samples

run_dir="$(ls -dt experiments/results/${NAME}_* 2>/dev/null | head -1)"
python experiments/verify_estimate_vs_actual.py --run-dir "$run_dir" \
  --json-out "$run_dir/verification_report.json" || true

python - <<PY
import json
from pathlib import Path
from src.core.model import fit_model

run_dir = Path("$run_dir")
actual_files = sorted(run_dir.glob("batch_*.json"))
rows = json.loads(actual_files[-1].read_text())
if len(rows) < 42:
    raise SystemExit(f"refusing fit: {len(rows)}/42 points")
model = fit_model(rows)
out = run_dir / "fitted_model.json"
model.save(out)
print(f"Fitted {out} R2={model.r_squared} n={len(rows)}")
PY

python scripts/update_sheets_formulas.py || true

echo "=== RESUME MEDIUM GRID DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
