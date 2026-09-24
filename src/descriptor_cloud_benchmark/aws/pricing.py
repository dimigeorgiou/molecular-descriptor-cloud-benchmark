"""
AWS Batch / EC2 billing helpers for chemoinformatics experiments.

Batch job APIs do not return dollar amounts; cost is derived from container
vCPU, memory, and wall time (startedAt → stoppedAt) using regional c5 rates.
"""
from __future__ import annotations

from enum import Enum

# eu-central-1, c5 family (Batch CE chemo-ec2-*), approximate 2026-07.
SPOT_VCPU_HOUR_USD = 0.017
SPOT_GB_HOUR_USD = 0.002
ONDEMAND_VCPU_HOUR_USD = 0.0544  # ~3.2× spot
ONDEMAND_GB_HOUR_USD = 0.0064

# Warm-keeper CE pilot (pilot_coldstart_warmkeeper_ondemand_rep10).
CLUSTER_INIT_COLD_SEC = 140.0
CLUSTER_INIT_WARM_SEC = 55.0
SCHEDULING_WARM_SEC = 5.0


class PricingTier(str, Enum):
    SPOT = "spot"
    ON_DEMAND = "on_demand"


def tier_label(use_spot: bool) -> str:
    return "SPOT" if use_spot else "ON-DEMAND"


def tier_from_use_spot(use_spot: bool) -> PricingTier:
    return PricingTier.SPOT if use_spot else PricingTier.ON_DEMAND


def container_runtime_cost_usd(
    vcpus: float,
    memory_gb: float,
    runtime_sec: float,
    *,
    tier: PricingTier = PricingTier.SPOT,
) -> float:
    """Bill one container for ``runtime_sec`` at the chosen tier."""
    if runtime_sec <= 0:
        return 0.0
    hours = runtime_sec / 3600.0
    if tier == PricingTier.SPOT:
        rate = vcpus * SPOT_VCPU_HOUR_USD + memory_gb * SPOT_GB_HOUR_USD
    else:
        rate = vcpus * ONDEMAND_VCPU_HOUR_USD + memory_gb * ONDEMAND_GB_HOUR_USD
    return hours * rate


def cluster_billing_cost_usd(
    n_nodes: int,
    vcpus_per_node: float,
    gb_per_node: float,
    lifetime_sec: float,
    *,
    tier: PricingTier,
) -> float:
    """Approximate cluster cost while ``n_nodes`` containers are billed."""
    return container_runtime_cost_usd(
        n_nodes * vcpus_per_node,
        n_nodes * gb_per_node,
        lifetime_sec,
        tier=tier,
    )


def blended_cluster_init_sec(n_replicas: int) -> float:
    """Replica 1 cold, 2+ warm (20-min scale-down delay on CE)."""
    if n_replicas <= 1:
        return CLUSTER_INIT_COLD_SEC
    warm = CLUSTER_INIT_WARM_SEC
    cold = CLUSTER_INIT_COLD_SEC
    return (cold + warm * (n_replicas - 1)) / n_replicas


def grid_amortized_cluster_init_sec(n_cells: int) -> float:
    """Sequential grid: first cell cold, rest warm within scale-down window."""
    if n_cells <= 1:
        return CLUSTER_INIT_COLD_SEC
    return (CLUSTER_INIT_COLD_SEC + CLUSTER_INIT_WARM_SEC * (n_cells - 1)) / n_cells


def dual_tier_costs(
    n_nodes: int,
    vcpus_per_node: float,
    gb_per_node: float,
    lifetime_sec: float,
) -> tuple[float, float]:
    """Return (spot_usd, on_demand_usd) for the same cluster lifetime."""
    spot = cluster_billing_cost_usd(
        n_nodes, vcpus_per_node, gb_per_node, lifetime_sec, tier=PricingTier.SPOT
    )
    od = cluster_billing_cost_usd(
        n_nodes, vcpus_per_node, gb_per_node, lifetime_sec, tier=PricingTier.ON_DEMAND
    )
    return round(spot, 6), round(od, 6)
