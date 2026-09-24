#!/usr/bin/env python3
"""Generate residual YAMLs from tmp/final_campaign/residual_plan.json."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "tmp/final_campaign/residual_plan.json"
OUT = REPO / "experiments/configs/final/residual"


def main() -> None:
    gaps = json.loads(PLAN.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for g in gaps:
        name = g["name"]
        body = {
            "mode": "compute_only",
            "smiles_complexity": g["cx"],
            "descriptor_method": "default",
            "vcpus_per_node": 4,
            "gb_per_node": 8,
            "use_spot": g["use_spot"],
            "n_replicas": g["n_replicas"],
            "dataset_dir": "datasets/samples",
            "dataset_sizes": [g["D"]],
            "node_configs": g["N"],
        }
        path = OUT / f"{name}.yaml"
        text = (
            f"# Residual final-campaign config (auto)\n"
            f"# wave={g['wave']} closes paper limitations gap\n"
            f"name: {name}\n"
        ) + yaml.dump(body, default_flow_style=False, sort_keys=False)
        path.write_text(text)
        written.append(path.relative_to(REPO))
    print(f"Wrote {len(written)} → {OUT}")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    main()
