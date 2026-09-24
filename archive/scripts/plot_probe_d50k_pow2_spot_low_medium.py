#!/usr/bin/env python3
"""Plot D=50k Spot pow2 sweep: low vs medium cluster_parallel medians."""
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
    low = medians_by_n("probe_d50k_pow2_spot_low", rows, hdr)
    med = medians_by_n("probe_d50k_pow2_spot_medium", rows, hdr)
    nodes = sorted(set(low) | set(med))

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=120)
    fig.patch.set_facecolor("#FAFAF8")
    ax.set_facecolor("#FAFAF8")
    ax.grid(True, alpha=0.3, color="#E8E8E4")

    if low:
        x = [n for n in nodes if n in low]
        y = [low[n] for n in x]
        ax.plot(x, y, "o-", color="#2E7D32", lw=2, ms=8, label="low")
        i = min(range(len(x)), key=lambda j: y[j])
        ax.annotate(f"low min N={x[i]}", (x[i], y[i]), xytext=(6, 6), textcoords="offset points", fontsize=8, color="#2E7D32")

    if med:
        x = [n for n in nodes if n in med]
        y = [med[n] for n in x]
        ax.plot(x, y, "s-", color="#E65100", lw=2, ms=7, label="medium")
        i = min(range(len(x)), key=lambda j: y[j])
        ax.annotate(f"med min N={x[i]}", (x[i], y[i]), xytext=(6, -14), textcoords="offset points", fontsize=8, color="#E65100")

    ax.set_xscale("log", base=2)
    ax.set_xticks(nodes)
    ax.set_xticklabels([str(n) for n in nodes])
    ax.set_xlabel("Nodes (N)")
    ax.set_ylabel("cluster_parallel median (s)")
    ax.set_title("D=50k Spot — 2 replicas, pow2 sweep")
    ax.legend(frameon=False)
    plt.tight_layout()

    out = REPO / "tmp" / "probe_d50k_pow2_spot_low_medium_viz.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(out)

    summary = {"low": low, "medium": med}
    (REPO / "tmp" / "probe_d50k_pow2_spot_low_medium_summary.json").write_text(
        json.dumps(summary, indent=2)
    )


if __name__ == "__main__":
    main()
