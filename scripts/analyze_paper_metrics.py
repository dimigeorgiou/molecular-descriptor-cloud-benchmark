#!/usr/bin/env python3
"""Analyze paper replication timing metrics from Sheets + local JSON."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FAILED_PAIRS = {
    "low": [(5000, 150), (5000, 185), (10000, 185), (20000, 185), (50000, 50)],
    "medium": [(5000, 150), (5000, 185), (10000, 185), (20000, 185), (30000, 100)],
}


def shape(pts: list[tuple[int, float]]) -> tuple[str, tuple[int, float]]:
    ts = [t for _, t in pts]
    imin = min(range(len(ts)), key=lambda i: ts[i])
    if all(ts[i] <= ts[i + 1] for i in range(len(ts) - 1)):
        return "monotone_up", pts[imin]
    if all(ts[i] >= ts[i + 1] for i in range(len(ts) - 1)):
        return "monotone_down", pts[imin]
    if imin == 0 or imin == len(ts) - 1:
        return "edge_min", pts[imin]
    return "interior_U", pts[imin]


def main() -> None:
    load_dotenv()
    from descriptor_cloud_benchmark.monitoring.sheets import read_results_rows

    sid = os.environ.get("GOOGLE_SHEETS_ID")
    if not sid:
        raise SystemExit("GOOGLE_SHEETS_ID not set")
    rows = read_results_rows(sid)
    hdr = rows[0]
    idx = {h: i for i, h in enumerate(hdr)}

    def col(row: list[str], name: str, default: float = 0.0) -> float:
        i = idx.get(name)
        if i is None or i >= len(row) or row[i] == "":
            return default
        return float(row[i])

    # Latest SUCCEEDED row per (exp, D, N)
    latest: dict[tuple[str, int, int], dict] = {}
    for row in rows[1:]:
        exp = row[idx["Experiment ID"]]
        if "paper_replication" not in exp or row[idx["Mode"]] != "compute_only":
            continue
        if row[idx["Status"]] != "SUCCEEDED":
            continue
        d = int(float(row[idx["Dataset Size (D)"]]))
        n = int(float(row[idx["Nodes (N)"]]))
        key = (exp, d, n)
        ts = row[idx["Timestamp"]]
        if key not in latest or ts > latest[key]["ts"]:
            s3 = col(row, "S3 Upload (s)")
            init = col(row, "Cluster Init (s)")
            par = col(row, "Cluster Parallel (s)")
            wall = col(row, "Wall Clock (s)", s3 + init + par)
            latest[key] = {
                "ts": ts,
                "complexity": row[idx["SMILES Complexity"]],
                "D": d,
                "N": n,
                "O": col(row, "Total Pipeline (s)"),
                "comp": col(row, "Computation (s)"),
                "wall": wall,
                "par": par,
            }

    print(f"Latest SUCCEEDED paper rows: {len(latest)}")
    for comp, pairs in FAILED_PAIRS.items():
        exp = f"paper_replication_{comp}_compute_only"
        for d, n in pairs:
            st = "OK" if (exp, d, n) in latest else "MISSING"
            print(f"  retry {comp} D={d} N={n}: {st}")

    metrics = [
        ("wall_clock (W)", "wall"),
        ("total_pipeline (O)", "O"),
        ("computation (L)", "comp"),
    ]
    out_path = REPO / "tmp" / "paper_metrics_analysis.json"
    report: dict = {"latest_succeeded_count": len(latest), "by_complexity": {}}

    for comp in ("low", "medium"):
        exp = f"paper_replication_{comp}_compute_only"
        pts_by_d: dict[int, list] = {d: [] for d in [5000, 10000, 20000, 30000, 40000, 50000]}
        for (e, d, n), v in latest.items():
            if e != exp:
                continue
            pts_by_d[d].append((n, v))
        comp_report = {}
        for mname, key in metrics:
            counts = {"interior_U": 0, "edge_min": 0, "monotone_up": 0, "monotone_down": 0}
            u_details = []
            for d in sorted(pts_by_d):
                pts = sorted((n, v[key]) for n, v in pts_by_d[d])
                if len(pts) < 4:
                    continue
                s, best = shape(pts)
                counts[s] = counts.get(s, 0) + 1
                if s == "interior_U":
                    u_details.append({"D": d, "N_star": best[0], "T": round(best[1], 1)})
            comp_report[mname] = {"counts": counts, "interior_minima": u_details}
            print(f"\n{comp} / {mname}: {counts}")
            for u in u_details:
                print(f"  D={u['D']}: interior min N={u['N_star']} T={u['T']}s")
        report["by_complexity"][comp] = comp_report

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out_path}")
    print(
        "\nConclusion: use wall_clock (col W) for paper U-curve narrative; "
        "filter Status=SUCCEEDED; computation (L) is reference only."
    )


if __name__ == "__main__":
    main()
