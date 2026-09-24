"""Independent reviewer verification of WHY_LOW_R2_REPORT claims. Pure stdlib on purpose:
shares no numeric libraries with the original script, so agreement is real corroboration."""
import csv
import json
from pathlib import Path
from statistics import median

ROOT = Path("/Users/dimitriosgeorgiou/Desktop/git/chemoinformatics-descriptor-computation")
CSV = ROOT / "tmp/paper2_rebuild/corrected_sheet_succeeded.csv"

D_SCOPE = [5000, 10000, 20000, 30000, 40000, 50000]
N_SCOPE = [25, 50, 75, 100, 125, 150, 185]
CX = ["low", "medium"]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


rows = list(csv.DictReader(open(CSV)))
for r in rows:
    r["D"], r["N"] = num(r["D"]), num(r["N"])
    for m in ("RealWallClock", "RealComputation"):
        r[m] = num(r[m])

scoped = [r for r in rows if r["ModeNorm"] == "full_pipeline" and r["Complexity"] in CX
          and r["D"] in D_SCOPE and r["N"] in N_SCOPE]
succ = [r for r in scoped if r["RealStatus"].strip().upper() == "SUCCEEDED"]

cells = {}
for r in succ:
    cells.setdefault((r["Complexity"], r["D"], r["N"]), []).append(r)
elig_keys = {k for k, v in cells.items() if len(v) >= 3}
elig = [r for r in succ if (r["Complexity"], r["D"], r["N"]) in elig_keys]
for r in elig:
    r["tier"] = r["PricingTierNorm"] or "unknown"

out = {"inventory": {
    "total_rows": len(rows),
    "rows_by_mode": {m: sum(1 for r in rows if r["ModeNorm"] == m) for m in {r["ModeNorm"] for r in rows}},
    "scoped_rows": len(scoped), "scoped_success": len(succ),
    "eligible_rows": len(elig), "eligible_cells": len(elig_keys),
    "reps_min_med_max": [min(len(v) for v in cells.values()), median([len(v) for v in cells.values()]),
                         max(len(v) for v in cells.values())],
    "tier_counts": {t: sum(1 for r in elig if r["tier"] == t) for t in {r["tier"] for r in elig}},
    "tier_x_schema": {},
}}
for r in elig:
    k = f'{r["tier"]}|{r["schema"]}|is_shifted={r["is_shifted"]}'
    out["inventory"]["tier_x_schema"][k] = out["inventory"]["tier_x_schema"].get(k, 0) + 1


def solve(A, b):
    """Gaussian elimination with partial pivoting."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(M[i][c]))
        M[c], M[p] = M[p], M[c]
        for i in range(c + 1, n):
            f = M[i][c] / M[c][c]
            for j in range(c, n + 1):
                M[i][j] -= f * M[c][j]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def ols(X, y):
    """X includes intercept column. Returns coefficient vector."""
    p = len(X[0])
    A = [[sum(X[k][i] * X[k][j] for k in range(len(X))) for j in range(p)] for i in range(p)]
    b = [sum(X[k][i] * y[k] for k in range(len(X))) for i in range(p)]
    return solve(A, b)


def r2(y, pred):
    m = sum(y) / len(y)
    ss_t = sum((v - m) ** 2 for v in y)
    ss_r = sum((y[i] - pred[i]) ** 2 for i in range(len(y)))
    return 1 - ss_r / ss_t


def design(rs, kind):
    if kind == "christos":
        return [[1.0, r["N"], r["D"], r["N"] ** 2, r["N"] * r["D"]] for r in rs]
    if kind == "christos_cx":  # adds a complexity indicator
        return [[1.0, r["N"], r["D"], r["N"] ** 2, r["N"] * r["D"],
                 1.0 if r["Complexity"] == "medium" else 0.0] for r in rs]
    if kind == "amdahl":
        return [[1.0, r["D"] / r["N"], r["N"]] for r in rs]
    raise ValueError(kind)


def fit_eval(rs, metric, kind):
    use = [r for r in rs if r[metric] is not None]
    X, y = design(use, kind), [r[metric] for r in use]
    beta = ols(X, y)
    r2_in = r2(y, [sum(X[i][j] * beta[j] for j in range(len(beta))) for i in range(len(X))])
    # leave-one-cell-out
    keys = [(r["Complexity"], r["D"], r["N"]) for r in use]
    pred, actual = [], []
    for ck in sorted(set(keys)):
        tr = [i for i, k in enumerate(keys) if k != ck]
        te = [i for i, k in enumerate(keys) if k == ck]
        if len(tr) < 5:
            continue
        b2 = ols([X[i] for i in tr], [y[i] for i in tr])
        for i in te:
            pred.append(sum(X[i][j] * b2[j] for j in range(len(b2))))
            actual.append(y[i])
    return {"n": len(use), "r2_in": r2_in, "r2_loco": r2(actual, pred), "coef": beta}


out["models"] = {}
for metric in ("RealWallClock", "RealComputation"):
    out["models"][metric] = {k: fit_eval(elig, metric, k)
                             for k in ("christos", "amdahl", "christos_cx")}

# Variance decomposition, replicating the report's per-tier split, plus a pooled version.
def var_decomp(rs, label):
    y = [r["RealWallClock"] for r in rs if r["RealWallClock"] is not None]
    rs = [r for r in rs if r["RealWallClock"] is not None]
    g = {}
    for r in rs:
        g.setdefault((r["Complexity"], r["D"], r["N"]), []).append(r["RealWallClock"])
    grand = sum(y) / len(y)
    ss_t = sum((v - grand) ** 2 for v in y)
    ss_b = sum(len(v) * (sum(v) / len(v) - grand) ** 2 for v in g.values())
    ss_w = ss_t - ss_b
    G, n = len(g), len(y)
    msb = ss_b / max(G - 1, 1)
    msw = ss_w / max(n - G, 1)
    kbar = n / G
    den = msb + (kbar - 1) * msw
    return {"label": label, "n": n, "cells": G, "eta2_between": ss_b / ss_t,
            "within_over_total": ss_w / ss_t,
            "icc": (msb - msw) / den if den > 0 else None,
            "mean_reps_per_cell": kbar,
            "reps_per_cell_min": min(len(v) for v in g.values()),
            "reps_per_cell_max": max(len(v) for v in g.values())}


out["variance"] = [var_decomp([r for r in elig if r["tier"] == t], f"tier={t}")
                   for t in ("SPOT", "unknown")]
out["variance"].append(var_decomp(elig, "POOLED_all_tiers"))
out["variance_median_across_tiers_as_reported"] = median(
    [v["within_over_total"] for v in out["variance"][:2]])

# Noise ceiling: best possible R2 from an oracle that knows each cell's true mean.
wall = [r for r in elig if r["RealWallClock"] is not None]
cm = {}
for r in wall:
    cm.setdefault((r["Complexity"], r["D"], r["N"]), []).append(r["RealWallClock"])
cm = {k: sum(v) / len(v) for k, v in cm.items()}
out["oracle_cell_mean_r2_wall"] = r2([r["RealWallClock"] for r in wall],
                                     [cm[(r["Complexity"], r["D"], r["N"])] for r in wall])

# Aggregation test: historical fits used 42 samples per complexity (= 6 D x 7 N cell aggregates).
agg = {}
for metric in ("RealWallClock", "RealComputation"):
    agg[metric] = {}
    for cx in CX:
        pts = {}
        for r in elig:
            if r["Complexity"] == cx and r[metric] is not None:
                pts.setdefault((r["D"], r["N"]), []).append(r[metric])
        rs = [{"Complexity": cx, "D": d, "N": n, metric: median(v)} for (d, n), v in pts.items()]
        X, y = design(rs, "christos"), [r[metric] for r in rs]
        beta = ols(X, y)
        agg[metric][cx] = {
            "n_points": len(rs),
            "r2_in": r2(y, [sum(X[i][j] * beta[j] for j in range(5)) for i in range(len(X))]),
            "d_coef_N2": beta[3]}
out["aggregated_per_complexity_fits"] = agg

# Spearman rho(wall, N)
def spearman(a, b):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(len(ra)))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((x - mb) ** 2 for x in rb) ** 0.5
    return cov / (va * vb)


out["spearman_wall_vs_N"] = spearman([r["RealWallClock"] for r in wall], [r["N"] for r in wall])
out["spearman_wall_vs_D"] = spearman([r["RealWallClock"] for r in wall], [r["D"] for r in wall])

print(json.dumps(out, indent=2, default=str))
