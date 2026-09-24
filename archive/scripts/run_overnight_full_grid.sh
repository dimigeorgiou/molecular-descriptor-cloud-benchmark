#!/usr/bin/env bash
# Overnight: CE scale-down → OD shape (84) → Spot data (840). Unattended-safe.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.

exec python scripts/overnight_full_grid.py "$@"
