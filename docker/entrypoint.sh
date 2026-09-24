#!/usr/bin/env bash
set -euo pipefail
# Package is installed into the image or PYTHONPATH includes src/
export PYTHONPATH="${PYTHONPATH:-/app/src}"
exec python -m descriptor_cloud_benchmark.worker.batch_shard_worker
