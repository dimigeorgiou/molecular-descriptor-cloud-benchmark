"""
Compare empirical paper_alignment_mini timings to paper reference model.

Uses saved run artifacts when present; skips otherwise.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINI_RUN = PROJECT_ROOT / "experiments/results/paper_alignment_mini_20260707_233519"
MINI_JSON = MINI_RUN / "local_compute_only_20260707_233529.json"


@pytest.mark.skipif(not MINI_JSON.exists(), reason="paper_alignment_mini run not found")
def test_d10k_local_within_3x_of_paper_reference() -> None:
    """D=10k N=50 local full-shard time should be same order of magnitude as paper ~199s."""
    from descriptor_cloud_benchmark.core.model import ModelCoefficients

    rows = json.loads(MINI_JSON.read_text())
    d10k = [r for r in rows if r["dataset_size"] == 10000]
    assert d10k
    actual_max = max(r["computation_sec"] for r in d10k)

    paper = ModelCoefficients.placeholder_defaults()
    n_ref = paper.optimal_nodes(10_000)
    paper_ref = paper.predict(n_ref, 10_000)

    ratio = actual_max / paper_ref
    assert 0.25 <= ratio <= 3.0, (
        f"actual_max={actual_max:.1f}s vs paper_ref={paper_ref:.1f}s (ratio={ratio:.2f})"
    )


@pytest.mark.skipif(not MINI_JSON.exists(), reason="paper_alignment_mini run not found")
def test_real_compute_not_plumbing_fast() -> None:
    """D=5000 must take >>1s (rules out hello-world Batch container behavior)."""
    rows = json.loads(MINI_JSON.read_text())
    d5k = [r for r in rows if r["dataset_size"] == 5000]
    assert min(r["computation_sec"] for r in d5k) > 10.0
