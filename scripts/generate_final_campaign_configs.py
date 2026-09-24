#!/usr/bin/env python3
"""Emit experiment YAMLs from experiments/configs/final/manifest.yaml."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "experiments/configs/final/manifest.yaml"
OUT_DIR = REPO / "experiments/configs/final"


def _header(name: str, wave: dict) -> str:
    return (
        f"# Auto-generated from manifest.yaml — do not edit by hand.\n"
        f"# Wave {wave['id']}: {wave['title']}\n"
        f"# Paper: {wave.get('limitation', '')}\n"
        f"name: {name}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    with open(args.manifest) as f:
        data = yaml.safe_load(f)

    defaults = data.get("defaults", {})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for wave in data["waves"]:
        for cfg in wave["configs"]:
            name = cfg["name"]
            body: dict = {
                "mode": cfg.get("mode", defaults.get("mode", "compute_only")),
                "smiles_complexity": cfg["smiles_complexity"],
                "descriptor_method": cfg.get(
                    "descriptor_method", defaults.get("descriptor_method", "default")
                ),
                "vcpus_per_node": cfg.get(
                    "vcpus_per_node", defaults.get("vcpus_per_node", 4)
                ),
                "gb_per_node": cfg.get("gb_per_node", defaults.get("gb_per_node", 8)),
                "use_spot": cfg["use_spot"],
                "n_replicas": cfg["n_replicas"],
                "dataset_dir": cfg.get(
                    "dataset_dir", defaults.get("dataset_dir", "datasets/samples")
                ),
            }
            if "grid_pairs" in cfg:
                body["grid_pairs"] = cfg["grid_pairs"]
            else:
                body["dataset_sizes"] = cfg["dataset_sizes"]
                body["node_configs"] = cfg["node_configs"]

            out_path = args.out_dir / f"{name}.yaml"
            payload = _header(name, wave) + yaml.dump(
                body, default_flow_style=False, sort_keys=False
            )
            out_path.write_text(payload)
            written.append(out_path)

    print(f"Wrote {len(written)} configs → {args.out_dir}")
    for p in written:
        print(f"  {p.relative_to(REPO)}")


if __name__ == "__main__":
    main()
