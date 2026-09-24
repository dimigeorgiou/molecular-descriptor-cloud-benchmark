#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate venv_chemoinformatics
set -a && source .env && set +a
export PYTHONPATH=.
exec python scripts/resume_overnight_grid.py "$@"
