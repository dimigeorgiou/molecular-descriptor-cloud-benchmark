"""Second reviewer pass: uncertainty on the headline R2 gaps (cell-level bootstrap)."""
import csv
import json
import random
from pathlib import Path

ROOT = Path("/Users/dimitriosgeorgiou/Desktop/git/chemoinformatics-descriptor-computation")
CSV = ROOT / "tmp/paper2_rebuild/corrected_sheet_succeeded.csv"
D_SCOPE = [5000, 10000, 20000, 30000, 40000, 50000]
N_SCOPE = [25, 50, 75, 100, 125, 150, 185]


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
scoped = [r for r in rows if r["ModeNorm"] == "full_pipeline" and r["Complexity"] in ("low", "medium")
          and r["D"] in D_SCOPE and r["N"] in N_SCOPE and r["RealStatus"].strip().upper() == "SUCCEEDED"]
cells = {}
for r in scoped:
    cells.setdefault((r["Complexity"], r["D"], r["N"]), []).append(r)
cells = {k: v for k, v in cells.items() if len(v) >= 3}


def solve(A, b):
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(M[i][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-300:
            return None
        for i in range(c + 1, n):
            f = M[i][c] / M[c][c]
            for j in range(c, n + 1):
                M[i][j] -= f * M[c][j]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def ols(X, y):
    p = len(X[0])
    A = [[sum(X[k][i] * X[k][j] for k in range(len(X))) for j in range(p)] for i in range(p)]
    b = [sum(X[k][i] * y[k] for k in range(len(X))) for i in range(p)]
    return solve(A, b)


def r2(y, pred):
    m = sum(y) / len(y)
    st = sum((v - m) ** 2 for v in y)
    return 1 - sum((y[i] - pred[i]) ** 2 for i in range(len(y))) / st if st > 0 else float("nan")


def des(rs, kind, metric):
    if kind == "christos":
        return [[1.0, r["N"], r["D"], r["N"] ** 2, r["N"] * r["D"]] for r in rs]
    return [[1.0, r["D"] / r["N"], r["N"]] for r in rs]


def fit_r2(rs, kind, metric):
    use = [r for r in rs if r[metric] is not None]
    X, y = des(use, kind, metric), [r[metric] for r in use]
    b = ols(X, y)
    if b is None:
        return None
    return r2(y, [sum(X[i][j] * b[j] for j in range(len(b))) for i in range(len(X))]), b


def oracle_r2(rs, metric):
    use = [r for r in rs if r[metric] is not None]
    g = {}
    for i, r in enumerate(use):
        g.setdefault((r["Complexity"], r["D"], r["N"]), []).append(r[metric])
    cm = {k: sum(v) / len(v) for k, v in g.items()}
    return r2([r[metric] for r in use],
              [cm[(r["Complexity"], r["D"], r["N"])] for r in use])


random.seed(7)
keys = list(cells)
B = 600
res = {k: [] for k in ("wall_christos", "wall_amdahl", "wall_diff_amd_minus_chr", "wall_oracle",
                       "comp_christos", "comp_minus_wall_christos", "wall_d_N2", "comp_d_N2")}
for _ in range(B):
    samp = [random.choice(keys) for _ in keys]
    rs = [r for k in samp for r in cells[k]]
    fw = fit_r2(rs, "christos", "RealWallClock")
    fa = fit_r2(rs, "amdahl", "RealWallClock")
    fc = fit_r2(rs, "christos", "RealComputation")
    if not (fw and fa and fc):
        continue
    res["wall_christos"].append(fw[0])
    res["wall_amdahl"].append(fa[0])
    res["wall_diff_amd_minus_chr"].append(fa[0] - fw[0])
    res["wall_oracle"].append(oracle_r2(rs, "RealWallClock"))
    res["comp_christos"].append(fc[0])
    res["comp_minus_wall_christos"].append(fc[0] - fw[0])
    res["wall_d_N2"].append(fw[1][3])
    res["comp_d_N2"].append(fc[1][3])


def ci(v):
    v = sorted(v)
    n = len(v)
    return {"n_boot": n, "median": v[n // 2],
            "ci95": [v[int(0.025 * n)], v[int(0.975 * n)]],
            "frac_negative": sum(1 for x in v if x < 0) / n}


print(json.dumps({k: ci(v) for k, v in res.items() if v}, indent=2))
