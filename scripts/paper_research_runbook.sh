#!/usr/bin/env bash
# Interactive runbook: estimate → confirm → Batch run → verify loss.
# Usage (from repo root, after: conda activate venv_chemoinformatics):
#   chmod +x scripts/paper_research_runbook.sh
#   ./scripts/paper_research_runbook.sh
#
# Environment: load .env (AWS, S3, BATCH queue/definition, GOOGLE_SHEETS_ID optional).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.

# shellcheck source=/dev/null
[[ -f .env ]] && source .env

COMPUTE_CFG="experiments/configs/paper_replication_low_compute_only.yaml"
FULL_CFG="experiments/configs/paper_replication_low_full_pipeline.yaml"
TS="$(date +%Y%m%d_%H%M%S)"

echo "=== STEP A — Preflight: datasets + validate_setup ==="
echo "Ensure datasets/samples/smiles_{5000..50000}_low.csv exist (see README)."
python scripts/validate_setup.py

echo ""
echo "=== STEP B — Estimation: compute_only grid (saved JSON) ==="
python experiments/estimator/experiment_estimator.py \
  --config "$COMPUTE_CFG" \
  --dataset-dir datasets/samples \
  --verbose \
  --save "experiments/results/estimate_preflight_compute_${TS}.json"

echo ""
echo "=== STEP C — Estimation: full_pipeline grid (saved JSON) ==="
python experiments/estimator/experiment_estimator.py \
  --config "$FULL_CFG" \
  --dataset-dir datasets/samples \
  --verbose \
  --save "experiments/results/estimate_preflight_full_${TS}.json"

echo ""
echo "Review total_time_hours and total_cost_usd in the JSON files above."
read -r -p "Press Enter to launch Batch for COMPUTE_ONLY (42 jobs), or Ctrl+C to stop..."
python experiments/run_experiment.py --config "$COMPUTE_CFG"

echo ""
read -r -p "Press Enter to launch Batch for FULL_PIPELINE (42 jobs), or Ctrl+C to stop..."
python experiments/run_experiment.py --config "$FULL_CFG"

echo ""
echo "=== STEP D — Verify loss (pre-run estimate lives under each run folder) ==="
echo "After each run_experiment.py --config … you get:"
echo "  experiments/results/<name>_<run_ts>/estimation/estimate.json"
echo "  experiments/results/<name>_<run_ts>/batch_<mode>_<run_ts>.json"
echo ""
echo "Single run folder:"
echo "  python experiments/verify_estimate_vs_actual.py \\"
echo "    --run-dir experiments/results/paper_replication_low_compute_only_<RUN_TS> \\"
echo "    --json-out experiments/results/verification_compute_<RUN_TS>.json"
echo ""
echo "Optional: still use standalone preflight JSONs from STEP B/C with --estimate/--actual."
echo "All runs for one config name:"
echo "  python experiments/verify_estimate_vs_actual.py \\"
echo "    --from-config $COMPUTE_CFG \\"
echo "    --json-out experiments/results/verification_all_compute_runs.json"
