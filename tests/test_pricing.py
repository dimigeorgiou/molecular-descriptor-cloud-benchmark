"""Tests for AWS pricing helpers."""
from __future__ import annotations

from descriptor_cloud_benchmark.aws.pricing import (
    PricingTier,
    blended_cluster_init_sec,
    container_runtime_cost_usd,
    dual_tier_costs,
    tier_label,
)


def test_on_demand_cost_higher_than_spot() -> None:
    spot = container_runtime_cost_usd(4, 8, 3600, tier=PricingTier.SPOT)
    od = container_runtime_cost_usd(4, 8, 3600, tier=PricingTier.ON_DEMAND)
    assert od > spot
    assert od / spot > 2.5


def test_blended_init_between_cold_and_warm() -> None:
    b = blended_cluster_init_sec(10)
    assert 55 < b < 140


def test_dual_tier_costs() -> None:
    spot, od = dual_tier_costs(25, 4, 8, 120.0)
    assert od > spot > 0


def test_tier_label() -> None:
    assert tier_label(True) == "SPOT"
    assert tier_label(False) == "ON-DEMAND"
