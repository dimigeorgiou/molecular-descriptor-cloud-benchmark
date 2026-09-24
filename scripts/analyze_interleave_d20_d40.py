#!/usr/bin/env python3
"""Compare interleaved D=20k/D=40k 2-rep run vs residual_w4 (batched by D)."""
from __future__ import annotations

import json
import os
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

POW2 = [2, 4, 8, 16, 32, 64, 128]


def _load_dotenv() -> None:
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _g(r, h, k) -> str:
    i = h[k]
    return r[i].strip() if i < len(r) else ""


def _means(bucket: dict, d: int, cx: str, n: int) -> tuple[float | None, int]:
    xs = bucket.get((d, cx, n), [])
    if not xs:
        return None, 0
    return st.mean(xs), len(xs)


def main() -> None:
    _load_dotenv()
    from src.monitoring.sheets import read_results_rows

    sheet_id = os.getenv("GOOGLE_SHEETS_ID") or "1jKcVFH-CB_sEmXffemcylaY65eUTMCa0jY8fv8lftbs"
    rows = read_results_rows(sheet_id, limit=20000)
    h = {n: i for i, n in enumerate(rows[0])}

    w4_comp: dict[tuple, list[float]] = defaultdict(list)
    w4_wall: dict[tuple, list[float]] = defaultdict(list)
    il_comp: dict[tuple, list[float]] = defaultdict(list)
    il_wall: dict[tuple, list[float]] = defaultdict(list)
    il_n = 0
    w4_n = 0

    for r in rows[1:]:
        if _g(r, h, "Status") != "SUCCEEDED":
            continue
        try:
            d = int(float(_g(r, h, "Dataset Size (D)")))
            n = int(float(_g(r, h, "Nodes (N)")))
            comp = float(_g(r, h, "Computation (s)"))
        except Exception:
            continue
        cx = _g(r, h, "SMILES Complexity").lower()
        if d not in (20000, 40000) or cx not in ("low", "medium"):
            continue
        exp = _g(r, h, "Experiment ID")
        try:
            wall = float(_g(r, h, "Wall Clock (s)") or _g(r, h, "Total Pipeline (s)"))
        except Exception:
            wall = None
        key = (d, cx, n)
        if exp.startswith("residual_w4"):
            w4_comp[key].append(comp)
            if wall is not None:
                w4_wall[key].append(wall)
            w4_n += 1
        if exp.startswith("interleave_"):
            il_comp[key].append(comp)
            if wall is not None:
                il_wall[key].append(wall)
            il_n += 1

    def table(title: str, a: dict, b: dict) -> list[float]:
        print(f"\n=== {title} ===")
        print(f"{'cell':<16} {'d20':>9} {'d40':>9} {'Δ%':>8} {'n20/n40':>8}")
        pcts = []
        for cx in ("low", "medium"):
            for n in POW2:
                ma, na = _means(a, 20000, cx, n)
                mb, nb = _means(b, 40000, cx, n) if a is b else _means(a, 40000, cx, n)
                # same dict: compare D=20 vs D=40 within that campaign
                mb, nb = _means(a, 40000, cx, n)
                if ma is None or mb is None:
                    print(f"{cx:7} N={n:<4} MISSING n={na}/{nb}")
                    continue
                pct = (mb - ma) / ma * 100
                pcts.append(pct)
                print(f"{cx:7} N={n:<4} {ma:9.3f} {mb:9.3f} {pct:7.1f}% {na}/{nb}")
        if pcts:
            print(
                f"Δ% median={st.median(pcts):.1f} mean={st.mean(pcts):.1f} "
                f"min={min(pcts):.1f} max={max(pcts):.1f}"
            )
        return pcts

    print(f"Sheets rows: residual_w4={w4_n} interleave={il_n}")
    w4_pct = table("residual_w4 Computation (batched by D)", w4_comp, w4_comp)
    il_pct = table("interleave Computation (cell-by-cell D)", il_comp, il_comp)
    table("residual_w4 Wall Clock", w4_wall, w4_wall)
    table("interleave Wall Clock", il_wall, il_wall)

    # within-cell replica swing (max-min)/mean
    def replica_swing(bucket: dict, label: str) -> None:
        swings = []
        print(f"\n=== within-cell replica swing {label} (range/mean) ===")
        for cx in ("low", "medium"):
            for d in (20000, 40000):
                for n in POW2:
                    xs = bucket.get((d, cx, n), [])
                    if len(xs) < 2:
                        continue
                    mean = st.mean(xs)
                    rng = (max(xs) - min(xs)) / mean * 100 if mean else 0
                    swings.append(rng)
        if swings:
            print(
                f"n_cells={len(swings)} median={st.median(swings):.1f}% "
                f"mean={st.mean(swings):.1f}% max={max(swings):.1f}%"
            )
        else:
            print("insufficient replica pairs")

    replica_swing(w4_comp, "w4 computation")
    replica_swing(il_comp, "interleave computation")
    replica_swing(w4_wall, "w4 wall")
    replica_swing(il_wall, "interleave wall")

    verdict = []
    if not il_pct:
        verdict.append("Interleave campaign has no SUCCEEDED rows yet.")
    else:
        # Expected D-scaling is ~+100% (2× molecules). Time-of-day Spot would
        # inflate wall Δ% scatter vs computation Δ%.
        w4_wall_pcts = []
        il_wall_pcts = []
        for cx in ("low", "medium"):
            for n in POW2:
                ma, _ = _means(w4_wall, 20000, cx, n)
                mb, _ = _means(w4_wall, 40000, cx, n)
                if ma and mb:
                    w4_wall_pcts.append((mb - ma) / ma * 100)
                ma, _ = _means(il_wall, 20000, cx, n)
                mb, _ = _means(il_wall, 40000, cx, n)
                if ma and mb:
                    il_wall_pcts.append((mb - ma) / ma * 100)
        print("\n=== verdict inputs ===")
        print(f"w4  compute Δ% median={st.median(w4_pct):.1f}  wall Δ% median={st.median(w4_wall_pcts):.1f}  wall Δ% range={max(w4_wall_pcts)-min(w4_wall_pcts):.1f}")
        print(f"intl compute Δ% median={st.median(il_pct):.1f}  wall Δ% median={st.median(il_wall_pcts):.1f}  wall Δ% range={max(il_wall_pcts)-min(il_wall_pcts):.1f}")
        wall_scatter_drop = (max(w4_wall_pcts) - min(w4_wall_pcts)) - (
            max(il_wall_pcts) - min(il_wall_pcts)
        )
        if st.median(il_pct) > 80:
            verdict.append(
                "Computation still ~2× at D=40k vs D=20k when interleaved "
                "→ D-scaling, not time-of-day Spot."
            )
        if wall_scatter_drop > 15:
            verdict.append(
                "Wall-clock D=40k/D=20k Δ% scatter shrank when interleaved "
                "→ part of the wall swing was time-of-day / Spot queueing."
            )
        elif wall_scatter_drop < -15:
            verdict.append(
                "Wall-clock scatter did not shrink (or grew) when interleaved "
                "→ time-of-day batching is not the main wall-clock driver."
            )
        else:
            verdict.append(
                "Wall-clock Δ% scatter similar batched vs interleaved "
                "→ time-of-day Spot is not a large extra effect beyond D-scaling."
            )

    print("\n=== VERDICT ===")
    for line in verdict:
        print(line)

    out = REPO / "tmp/final_campaign/interleave/analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "w4_rows": w4_n,
                "interleave_rows": il_n,
                "w4_compute_delta_pct": w4_pct,
                "interleave_compute_delta_pct": il_pct,
                "verdict": verdict,
            },
            indent=2,
        )
    )
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
