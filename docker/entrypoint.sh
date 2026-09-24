#!/usr/bin/env bash
set -euo pipefail
exec python -m src.worker.batch_shard_worker
