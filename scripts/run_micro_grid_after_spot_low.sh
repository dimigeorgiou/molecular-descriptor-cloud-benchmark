#!/usr/bin/env bash
# After resume spot_low finishes, run partial micro-grid (parallel with spot_medium).
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RESUME_LOG="$ROOT/tmp/overnight_run.log"
WAIT_LOG="$ROOT/tmp/micro_grid_low_n_wait.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WAIT: $*" | tee -a "$WAIT_LOG"; }

spot_low_done() {
  grep -q "RESUME: A_spot: spot_medium" "$RESUME_LOG" 2>/dev/null && return 0
  grep -q "RESUME: A_spot: spot_low — nothing remaining" "$RESUME_LOG" 2>/dev/null && return 0
  return 1
}

log "Waiting for resume spot_low to finish (then start partial micro-grid)..."
while ! spot_low_done; do
  sleep 60
  log "still waiting (spot_low in progress; resume continues)..."
done

log "spot_low done — starting partial micro-grid (OD low + Spot medium)"
exec bash "$ROOT/scripts/run_micro_grid_low_n.sh" \
  --config micro_grid_low_n_low_ondemand.yaml \
  --config micro_grid_low_n_medium_spot.yaml
