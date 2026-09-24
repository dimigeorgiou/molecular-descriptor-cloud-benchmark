#!/usr/bin/env python3
"""
Analyze cold-start decay: cluster_init_sec vs replica order (not Spot vs On-Demand).

Reads Sheets or local batch JSON for experiment pilot_coldstart_decay_ondemand_rep10
(or --experiment-id override).

Outputs tmp/coldstart_decay_report.json with:
  - per-replica init times
  - corr(replica_order, cluster_init_sec)
  - replica-1 vs replicas-2+ summary
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from statistics import mean, stdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.core.replica_analysis import coefficient_of_variation


def _pearson_r(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n < 3 or len(ys) != n:
        return float("nan"), float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return float("nan"), float("nan")
    r = num / (den_x * den_y)
    if abs(r) >= 1:
        return r, 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    from math import erf

    p = 2 * (1 - (0.5 + 0.5 * erf(abs(t) / math.sqrt(2))))
    return r, min(1.0, max(0.0, p))


def load_from_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else data.get("runs", [])


def load_from_sheets(sheet_id: str) -> list[dict]:
    from dotenv import load_dotenv

    load_dotenv()
    from src.monitoring.sheets import read_results_rows

    raw = read_results_rows(sheet_id)
    if not raw:
        return []
    hdr = {h: i for i, h in enumerate(raw[0])}

    def col(row: list[str], name: str, default: str = "") -> str:
        i = hdr.get(name)
        return row[i] if i is not None and i < len(row) else default

    rows: list[dict] = []
    for row in raw[1:]:
        notes = col(row, "Notes")
        replica_index = 0
        if "replica=" in notes:
            try:
                part = notes.split("replica=")[1].split("/")[0].split(";")[0].strip()
                replica_index = max(0, int(part) - 1)
            except (ValueError, IndexError):
                pass
        rows.append(
            {
                "experiment_id": col(row, "Experiment ID"),
                "dataset_size": int(float(col(row, "Dataset Size (D)", "0") or 0)),
                "n_nodes": int(float(col(row, "Nodes (N)", "0") or 0)),
                "status": col(row, "Status"),
                "cluster_init_sec": float(col(row, "Cluster Init (s)", "0") or 0),
                "wall_clock_sec": float(col(row, "Wall Clock (s)", "0") or 0),
                "replica_index": replica_index,
                "notes": notes,
            }
        )
    return rows


def analyze(rows: list[dict], *, experiment_id: str, d: int, n: int) -> dict:
    filtered = [
        r
        for r in rows
        if r.get("experiment_id") == experiment_id
        and int(r.get("dataset_size", 0)) == d
        and int(r.get("n_nodes", 0)) == n
        and r.get("status") in ("SUCCEEDED", "completed", "")
    ]
    filtered.sort(key=lambda r: int(r.get("replica_index", 0)))

    if not filtered:
        return {"error": f"No SUCCEEDED rows for {experiment_id} D={d} N={n}"}

    orders = [float(i + 1) for i in range(len(filtered))]
    inits = [float(r["cluster_init_sec"]) for r in filtered]
    walls = [float(r.get("wall_clock_sec") or 0) for r in filtered]
    r_init, p_init = _pearson_r(orders, inits)

    first = inits[0]
    rest = inits[1:] if len(inits) > 1 else []
    report = {
        "experiment_id": experiment_id,
        "cell": {"D": d, "N": n},
        "n_replicas": len(filtered),
        "per_replica": [
            {
                "replica": i + 1,
                "cluster_init_sec": round(init, 3),
                "wall_clock_sec": round(wall, 3),
            }
            for i, (init, wall) in enumerate(zip(inits, walls))
        ],
        "cluster_init_sec": {
            "all_cv": round(coefficient_of_variation(inits), 4) if len(inits) > 1 else 0.0,
            "replica_1": round(first, 3),
            "replicas_2_plus_mean": round(mean(rest), 3) if rest else None,
            "replicas_2_plus_cv": round(coefficient_of_variation(rest), 4) if len(rest) > 1 else None,
            "cold_to_warm_ratio": round(first / mean(rest), 2) if rest and mean(rest) > 0 else None,
        },
        "corr_replica_order_init": {"r": round(r_init, 3), "p": round(p_init, 3)},
        "supports_cold_start_hypothesis": bool(
            len(inits) >= 3 and first > 2 * mean(rest) if rest else False
        ),
        "interpretation": (
            "Replica 1 init >> replicas 2+ — consistent with CE scale-from-zero cold start."
            if rest and first > 2 * mean(rest)
            else "Pattern unclear — check CE min vCPUs and scale-down delay."
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Local batch results JSON")
    parser.add_argument("--sheet-id", default=os.getenv("GOOGLE_SHEETS_ID"))
    parser.add_argument(
        "--experiment-id",
        default="pilot_coldstart_decay_ondemand_rep10",
    )
    parser.add_argument("--d", type=int, default=5000)
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--out", type=Path, default=REPO / "tmp" / "coldstart_decay_report.json")
    args = parser.parse_args()

    if args.json:
        rows = load_from_json(args.json)
    elif args.sheet_id:
        rows = load_from_sheets(args.sheet_id)
    else:
        raise SystemExit("Provide --json or GOOGLE_SHEETS_ID")

    report = analyze(rows, experiment_id=args.experiment_id, d=args.d, n=args.n)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))

    if "error" in report:
        print(report["error"])
        sys.exit(1)

    print(f"Experiment: {args.experiment_id} D={args.d} N={args.n} n={report['n_replicas']}")
    for row in report["per_replica"]:
        print(f"  replica {row['replica']:2d}: init={row['cluster_init_sec']}s wall={row['wall_clock_sec']}s")
    ci = report["cluster_init_sec"]
    print(f"\nReplica 1 init: {ci['replica_1']}s")
    print(f"Replicas 2+ mean: {ci['replicas_2_plus_mean']}s (CV={ci['replicas_2_plus_cv']})")
    print(f"Cold/warm ratio: {ci['cold_to_warm_ratio']}x")
    cr = report["corr_replica_order_init"]
    print(f"corr(order, init): r={cr['r']} p={cr['p']}")
    print(f"\n{report['interpretation']}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
