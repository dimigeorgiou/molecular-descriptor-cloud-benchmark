"""
Sanity-check paper reference predictions from ModelCoefficients defaults.

Paper Section 7 reference times (approximate):
  D=10_000 → ~199 s at optimal N
  D=50_000 → ~445 s at optimal N
"""
from __future__ import annotations

from src.core.model import ModelCoefficients


def test_paper_model_predicts_order_of_magnitude_at_10k() -> None:
    model = ModelCoefficients.placeholder_defaults()
    n_opt = model.optimal_nodes(10_000)
    t = model.predict(n_opt, 10_000)
    assert 50 <= t <= 500, f"expected ~199s order of magnitude, got {t}s at N={n_opt}"


def test_paper_model_predicts_order_of_magnitude_at_50k() -> None:
    model = ModelCoefficients.placeholder_defaults()
    n_opt = model.optimal_nodes(50_000)
    t = model.predict(n_opt, 50_000)
    assert 100 <= t <= 900, f"expected ~445s order of magnitude, got {t}s at N={n_opt}"
