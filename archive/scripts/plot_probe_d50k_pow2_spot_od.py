#!/usr/bin/env python3
"""Plot D=50k pow2 sweep: Spot vs On-Demand, low vs medium (from Sheets)."""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.monitoring.sheets import read_results_rows  # noqa: E402

SERIES = [
    ("probe_d50k_pow2_spot_low", "Spot low", "#2E7D32", "o", "-"),
    ("probe_d50k_pow2_spot_medium", "Spot medium", "#E65100", "s", "-"),
    ("probe_d50k_pow2_ondemand_low", "OD low", "#1565C0", "o", "--"),
    ("probe_d50k_pow2_ondemand_medium", "OD medium", "#6A1B9A", "s", "--"),
    ("probe_d50k_pow2_ondemand", "OD low (legacy 1-rep)", "#90CAF9", "o", ":"),
]


def medians_by_n(exp_id: str, rows: list[list[str]], hdr: list[str]) -> dict[int, float]:
    idx = {h: i for i, h in enumerate(hdr)}

    def get(r: list[str], col: str) -> str:
        i = idx.get(col)
        return r[i] if i is not None and i < len(r) else ""

    by_n: dict[int, list[float]] = defaultdict(list)
    for r in rows[1:]:
        if get(r, "Experiment ID") != exp_id:
            continue
        try:
            n = int(float(get(r, "Nodes (N)")))
            cp = float(get(r, "Cluster Parallel (s)"))
        except (TypeError, ValueError):
            continue
        by_n[n].append(cp)
    return {n: statistics.median(v) for n, v in sorted(by_n.items())}


def main() -> None:
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    if not sheet_id:
        raise SystemExit("GOOGLE_SHEETS_ID not set")

    rows = read_results_rows(sheet_id)
    hdr = rows[0]
    data: dict[str, dict[int, float]] = {}
    all_nodes: set[int] = set()
    for exp_id, *_ in SERIES:
        m = medians_by_n(exp_id, rows, hdr)
        if m:
            data[exp_id] = m
            all_nodes |= set(m)
    nodes = sorted(all_nodes)

    fig, ax = plt.subplots(figsize=(9, 5), dpi=120)
    fig.patch.set_facecolor("#FAFAF8")
    ax.set_facecolor("#FAFAF8")
    ax.grid(True, alpha=0.3, color="#E8E8E4")

    summary: dict[str, dict[str, float]] = {}
    for exp_id, label, color, marker, ls in SERIES:
        m = data.get(exp_id)
        if not m:
            continue
        x = [n for n in nodes if n in m]
        y = [m[n] for n in x]
        ax.plot(x, y, marker=marker, ls=ls, color=color, lw=2, ms=7, label=label)
        summary[label] = {str(k): v for k, v in m.items()}

    ax.set_xscale("log", base=2)
    ax.set_xticks(nodes)
    ax.set_xticklabels([str(n) for n in nodes])
    ax.set_xlabel("Nodes (N)")
    ax.set_ylabel("cluster_parallel median (s)")
    ax.set_title("D=50k pow2 — Spot vs On-Demand, low & medium (2 rep)")
    ax.legend(frameon=False, fontsize=9)
    plt.tight_layout()

    out = REPO / "tmp" / "probe_d50k_pow2_spot_od_viz.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(out)

    (REPO / "tmp" / "probe_d50k_pow2_spot_od_summary.json").write_text(
        json.dumps(summary, indent=2)
    )


if __name__ == "__main__":
    main()
