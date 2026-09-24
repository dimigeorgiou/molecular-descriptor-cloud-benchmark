#!/usr/bin/env bash
# Wait for overnight resume to finish, then run micro-grid low-N study.
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="$ROOT/tmp/micro_grid_low_n_wait.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WAIT: $*" | tee -a "$LOG"; }

log "Waiting for resume_overnight_grid.py to exit..."
while pgrep -f "resume_overnight_grid.py" >/dev/null 2>&1; do
  sleep 120
  log "still waiting (resume running)..."
done
log "Resume finished — starting micro-grid low-N"
exec bash "$ROOT/scripts/run_micro_grid_low_n.sh"
