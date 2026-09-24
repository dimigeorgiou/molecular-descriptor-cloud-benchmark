#!/usr/bin/env python3
"""9+ panel analytical visualization of pow2 low-N probe experiments (D=10k–50k)."""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.monitoring.sheets import read_results_rows  # noqa: E402

BG = "#FAFAF8"
GRID = "#E8E8E4"

EXP_MAP = {
    "spot_low": "probe_d50k_pow2_spot_low",
    "spot_med": "probe_d50k_pow2_spot_medium",
    "od_low": "probe_d50k_pow2_ondemand_low",
    "od_med": "probe_d50k_pow2_ondemand_medium",
    "d10k_spot": "probe_d10k_low_n_spot",
    "d20k_d40k_low": "probe_d20k_d40k_pow2_spot_low",
    "d20k_d40k_low_ext": "probe_d20k_d40k_pow2_spot_low_ext",
    "d20k_d40k_med": "probe_d20k_d40k_pow2_spot_medium",
    "d20k_d40k_med_ext": "probe_d20k_d40k_pow2_spot_medium_ext",
    "overnight_d50k": "overnight_spot_data_low",
}

POW2_FULL = [2, 4, 8, 16, 32, 64, 128]
MULTI_D = [10000, 20000, 40000, 50000]

# Paper analytical N* (from data/paper_fitted_model.json)
PAPER_NSTAR = {10000: 114, 20000: 128, 40000: 156, 50000: 170}


def load_series(rows: list[list[str]], hdr: list[str], exp_id: str, d: int | None = None):
    idx = {h: i for i, h in enumerate(hdr)}

    def get(r: list[str], col: str) -> str:
        i = idx.get(col)
        return r[i] if i is not None and i < len(r) else ""

    by_n: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: {"cp": [], "comp": [], "sched": [], "init": [], "cost": []}
    )
    for r in rows[1:]:
        if get(r, "Experiment ID") != exp_id:
            continue
        if d is not None:
            try:
                if int(float(get(r, "Dataset Size (D)"))) != d:
                    continue
            except (TypeError, ValueError):
                continue
        try:
            n = int(float(get(r, "Nodes (N)")))
        except (TypeError, ValueError):
            continue
        for key, col in [
            ("cp", "Cluster Parallel (s)"),
            ("comp", "Computation (s)"),
            ("sched", "Scheduling (s)"),
            ("init", "Cluster Init (s)"),
            ("cost", "Cost (USD)"),
        ]:
            try:
                by_n[n][key].append(float(get(r, col)))
            except (TypeError, ValueError):
                pass

    med = {}
    for n, buckets in sorted(by_n.items()):
        med[n] = {k: statistics.median(v) if v else float("nan") for k, v in buckets.items()}
        med[n]["n"] = max(len(buckets["cp"]), 0)
    return med


def xy(med: dict[int, dict], nodes: list[int] | None = None, field: str = "cp"):
    nodes = nodes or sorted(med)
    xs = [n for n in nodes if n in med]
    return xs, [med[n][field] for n in xs]


def mark_min(ax, xs, ys, color, label_prefix=""):
    if not xs:
        return
    i = int(np.nanargmin(ys))
    ax.annotate(
        f"{label_prefix}N={xs[i]}",
        (xs[i], ys[i]),
        xytext=(6, 6),
        textcoords="offset points",
        fontsize=7,
        color=color,
    )


def style_ax(ax, title: str, ylabel: str = "cluster_parallel (s)", xlabel: str = "Nodes (N)"):
    ax.set_facecolor(BG)
    ax.grid(True, alpha=0.3, color=GRID)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_xlabel(xlabel, fontsize=8)


def find_min(med: dict[int, dict]) -> dict | None:
    if not med:
        return None
    n = min(med, key=lambda k: med[k]["cp"])
    return {
        "N": n,
        "cluster_parallel": med[n]["cp"],
        "computation": med[n]["comp"],
        "scheduling": med[n]["sched"],
        "cost": med[n]["cost"],
    }


def fit_1d_quadratic(med: dict[int, dict], field: str = "cp") -> dict:
    """T(N)=α+βN+γN² → N*=-β/(2γ) when γ>0. Returns nan N_raw if non-convex."""
    pts = [(n, med[n][field]) for n in sorted(med) if field in med[n]]
    if len(pts) < 3:
        return {"N_raw": float("nan"), "N_clamp": None, "gamma": float("nan"), "r2": float("nan")}
    N = np.array([p[0] for p in pts], float)
    T = np.array([p[1] for p in pts], float)
    X = np.column_stack([np.ones_like(N), N, N**2])
    coef, *_ = np.linalg.lstsq(X, T, rcond=None)
    alpha, beta, gamma = coef
    ss_res = ((T - X @ coef) ** 2).sum()
    ss_tot = ((T - T.mean()) ** 2).sum() + 1e-12
    r2 = 1 - ss_res / ss_tot
    if gamma <= 0:
        return {
            "N_raw": float("nan"),
            "N_clamp": int(N[np.argmin(T)]),
            "gamma": float(gamma),
            "r2": float(r2),
            "convex": False,
        }
    n_raw = -beta / (2 * gamma)
    n_clamp = int(np.clip(round(n_raw), N.min(), N.max()))
    return {
        "N_raw": float(n_raw),
        "N_clamp": n_clamp,
        "gamma": float(gamma),
        "r2": float(r2),
        "convex": True,
        "alpha": float(alpha),
        "beta": float(beta),
    }


def fit_global_td(series_by_d: dict[int, dict[int, dict]]) -> dict:
    """OLS T(N,D)=a+bN+cD+dN²+eND on cluster_parallel medians."""
    from src.core.model import fit_model

    pts = []
    for d, by_n in series_by_d.items():
        for n, v in by_n.items():
            pts.append({"n_nodes": n, "dataset_size": d, "execution_time": v["cp"]})
    if len(pts) < 5:
        return {"ok": False}
    m = fit_model(pts)
    nstar = {}
    for D in [5000, 10000, 20000, 30000, 40000, 50000]:
        if m.d <= 0:
            nstar[D] = None
        else:
            nstar[D] = -(m.b + m.e * D) / (2 * m.d)
    return {
        "ok": True,
        "a": m.a,
        "b": m.b,
        "c": m.c,
        "d": m.d,
        "e": m.e,
        "r2": m.r_squared,
        "nstar_raw": nstar,
    }


def merge_series(*parts: dict[int, dict]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for part in parts:
        for n, v in part.items():
            out[n] = v
    return out


def load_merged_d(rows, hdr, base_key: str, ext_key: str, d: int) -> dict[int, dict]:
    base = load_series(rows, hdr, EXP_MAP[base_key], d)
    ext = load_series(rows, hdr, EXP_MAP[ext_key], d)
    return merge_series(base, ext)


def log_n_axis(ax, nodes: list[int]):
    ax.set_xscale("log", base=2)
    ax.set_xticks(nodes)
    ax.set_xticklabels(nodes)


def main() -> None:
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "")
    if not sheet_id:
        raise SystemExit("GOOGLE_SHEETS_ID not set")

    rows = read_results_rows(sheet_id)
    hdr = rows[0]

    spot_low = load_series(rows, hdr, EXP_MAP["spot_low"], 50000)
    spot_med = load_series(rows, hdr, EXP_MAP["spot_med"], 50000)
    od_low = load_series(rows, hdr, EXP_MAP["od_low"], 50000)
    od_med = load_series(rows, hdr, EXP_MAP["od_med"], 50000)
    d10k = load_series(rows, hdr, EXP_MAP["d10k_spot"], 10000)
    d20k_low = load_merged_d(rows, hdr, "d20k_d40k_low", "d20k_d40k_low_ext", 20000)
    d40k_low = load_merged_d(rows, hdr, "d20k_d40k_low", "d20k_d40k_low_ext", 40000)
    d20k_med = load_merged_d(rows, hdr, "d20k_d40k_med", "d20k_d40k_med_ext", 20000)
    d40k_med = load_merged_d(rows, hdr, "d20k_d40k_med", "d20k_d40k_med_ext", 40000)
    ov50 = load_series(rows, hdr, EXP_MAP["overnight_d50k"], 50000)

    d_med_map = {
        10000: d10k,
        20000: d20k_low,
        40000: d40k_low,
        50000: spot_low,
    }
    d_med_map_med = {
        20000: d20k_med,
        40000: d40k_med,
        50000: spot_med,
    }

    fig = plt.figure(figsize=(16, 14), dpi=140)
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(3, 3, hspace=0.42, wspace=0.32)

    # ── A: D=50k Spot low vs medium ──────────────────────────────────────
    ax = fig.add_subplot(gs[0, 0])
    style_ax(ax, "A · D=50k Spot — low vs medium")
    x, y = xy(spot_low, POW2_FULL)
    ax.plot(x, y, "o-", color="#2E7D32", lw=2, ms=5, label="low")
    mark_min(ax, x, y, "#2E7D32", "low ")
    x, y = xy(spot_med, POW2_FULL)
    ax.plot(x, y, "s-", color="#E65100", lw=2, ms=5, label="medium")
    mark_min(ax, x, y, "#E65100", "med ")
    log_n_axis(ax, POW2_FULL)
    ax.legend(frameon=False, fontsize=7)

    # ── B: D=50k Spot vs OD (low) ────────────────────────────────────────
    ax = fig.add_subplot(gs[0, 1])
    style_ax(ax, "B · D=50k low — Spot vs On-Demand")
    x, y = xy(spot_low, POW2_FULL)
    ax.plot(x, y, "o-", color="#2E7D32", lw=2, ms=5, label="Spot")
    x, y = xy(od_low, POW2_FULL)
    ax.plot(x, y, "o--", color="#1565C0", lw=2, ms=5, label="On-Demand")
    log_n_axis(ax, POW2_FULL)
    ax.legend(frameon=False, fontsize=7)

    # ── C: Multi-D Spot low U-curves ─────────────────────────────────────
    ax = fig.add_subplot(gs[0, 2])
    style_ax(ax, "C · Spot low — D=10k / 20k / 40k / 50k")
    for med, fmt, color, label in [
        (d10k, "^-", "#00897B", "D=10k"),
        (d20k_low, "o-", "#0277BD", "D=20k"),
        (d40k_low, "s-", "#6A1B9A", "D=40k"),
        (spot_low, "D-", "#2E7D32", "D=50k"),
    ]:
        x, y = xy(med, POW2_FULL if med is not d10k else None)
        if not x:
            continue
        ax.plot(x, y, fmt, color=color, lw=2, ms=5, label=label)
        mark_min(ax, x, y, color)
    ax.set_xscale("log", base=2)
    ax.legend(frameon=False, fontsize=7, loc="upper left")

    # ── D: Multi-D Spot medium U-curves ──────────────────────────────────
    ax = fig.add_subplot(gs[1, 0])
    style_ax(ax, "D · Spot medium — D=20k / 40k / 50k")
    for med, fmt, color, label in [
        (d20k_med, "o-", "#EF6C00", "D=20k"),
        (d40k_med, "s-", "#AD1457", "D=40k"),
        (spot_med, "D-", "#E65100", "D=50k"),
    ]:
        x, y = xy(med, POW2_FULL)
        if not x:
            continue
        ax.plot(x, y, fmt, color=color, lw=2, ms=5, label=label)
        mark_min(ax, x, y, color)
    log_n_axis(ax, POW2_FULL)
    ax.legend(frameon=False, fontsize=7)

    # ── E: N* vs D — argmin (artifact) vs fitted vertices vs paper ───────
    ax = fig.add_subplot(gs[1, 1])
    style_ax(
        ax,
        "E · N* vs D — fitted vertex (not discrete argmin)",
        ylabel="N* (nodes)",
        xlabel="Dataset size D",
    )
    ds_plot = [d for d in MULTI_D if d_med_map.get(d)]
    n_argmin = []
    n_local = []
    n_paper = []
    local_fits = {}
    for d in ds_plot:
        opt = find_min(d_med_map[d])
        n_argmin.append(opt["N"] if opt else np.nan)
        lf = fit_1d_quadratic(d_med_map[d])
        local_fits[d] = lf
        n_local.append(lf["N_raw"] if lf.get("convex") else np.nan)
        n_paper.append(PAPER_NSTAR.get(d, np.nan))

    global_fit = fit_global_td(d_med_map)
    ds_global = [5000, 10000, 20000, 30000, 40000, 50000]
    n_global = [
        global_fit["nstar_raw"].get(d) if global_fit.get("ok") else np.nan for d in ds_global
    ]
    # plot continuous global N* (may be negative at small D — show for trend)
    ax.plot(
        ds_global,
        n_global,
        "D-",
        color="#1565C0",
        lw=2.5,
        ms=7,
        label=f"global T(N,D) N* (R²={global_fit.get('r2', 0):.2f})",
    )
    ax.plot(
        ds_plot,
        n_local,
        "o-",
        color="#2E7D32",
        lw=2,
        ms=7,
        label="per-D quadratic N* (γ>0 only)",
    )
    ax.plot(
        ds_plot,
        n_argmin,
        "x:",
        color="#C62828",
        lw=1.5,
        ms=8,
        alpha=0.7,
        label="discrete argmin (pow2 grid — artifact risk)",
    )
    ax.plot(ds_plot, n_paper, "s--", color="#78909C", lw=1.5, ms=6, label="paper model N*")
    ax.axhline(0, color="#B0BEC5", lw=0.8)
    for d, n in zip(ds_global, n_global):
        if n is not None and not np.isnan(n) and n > 0:
            ax.annotate(f"{n:.0f}", (d, n), xytext=(3, 5), textcoords="offset points", fontsize=7, color="#1565C0")
    ax.legend(frameon=False, fontsize=6, loc="upper left")
    ax.set_ylim(bottom=-20)

    # ── F: cp at N* vs D (+ overnight N=25) ──────────────────────────────
    ax = fig.add_subplot(gs[1, 2])
    style_ax(ax, "F · Wall time at N* vs D", ylabel="cluster_parallel (s)", xlabel="Dataset size D")
    cp_opts = []
    cp25s = []
    for d in ds_plot:
        opt = find_min(d_med_map[d])
        cp_opts.append(opt["cluster_parallel"] if opt else np.nan)
        m25 = load_series(rows, hdr, EXP_MAP["overnight_d50k"], d)
        cp25s.append(m25[25]["cp"] if 25 in m25 else np.nan)
    ax.plot(ds_plot, cp_opts, "D-", color="#C62828", lw=2.5, ms=8, label="cp at N* (pow2)")
    ax.plot(ds_plot, cp25s, "s:", color="#78909C", lw=1.5, ms=6, label="cp @ N=25 overnight")
    ax.legend(frameon=False, fontsize=7)

    # ── G: Decomposition — compute vs scheduling (D=50k Spot low) ────────
    ax = fig.add_subplot(gs[2, 0])
    style_ax(ax, "G · D=50k Spot low — compute vs scheduling", ylabel="seconds")
    xs = [n for n in POW2_FULL if n in spot_low]
    comp = [spot_low[n]["comp"] for n in xs]
    sched = [spot_low[n]["sched"] for n in xs]
    w = 0.35
    xpos = np.arange(len(xs))
    ax.bar(xpos - w / 2, comp, w, color="#81C784", label="computation")
    ax.bar(xpos + w / 2, sched, w, color="#2E7D32", label="scheduling")
    ax.set_xticks(xpos)
    ax.set_xticklabels(xs)
    ax.legend(frameon=False, fontsize=7)

    # ── H: Cost frontier Spot vs OD (D=50k low) ──────────────────────────
    ax = fig.add_subplot(gs[2, 1])
    style_ax(ax, "H · Cost frontier D=50k low", ylabel="cost (USD)", xlabel="cluster_parallel (s)")
    for med, marker, color, label in [
        (spot_low, "o", "#2E7D32", "Spot"),
        (od_low, "s", "#1565C0", "On-Demand"),
    ]:
        cps, costs, ns = [], [], []
        for n in POW2_FULL:
            if n not in med:
                continue
            cps.append(med[n]["cp"])
            costs.append(med[n]["cost"])
            ns.append(n)
        ax.plot(cps, costs, f"{marker}-", color=color, lw=2, ms=6, label=label)
        for c, cost, n in zip(cps, costs, ns):
            ax.annotate(f"N={n}", (c, cost), fontsize=6, xytext=(3, 3), textcoords="offset points", color=color)
    ax.legend(frameon=False, fontsize=7)

    # ── I: Scheduling fraction + compute speedup ─────────────────────────
    ax = fig.add_subplot(gs[2, 2])
    style_ax(ax, "I · ★ Scheduling fraction of wall time", ylabel="sched / cluster_parallel")
    for med, fmt, color, label in [
        (d20k_low, "o-", "#0277BD", "D=20k"),
        (d40k_low, "s-", "#6A1B9A", "D=40k"),
        (spot_low, "D-", "#2E7D32", "D=50k"),
    ]:
        xs = [n for n in POW2_FULL if n in med]
        frac = [
            (med[n]["sched"] / med[n]["cp"]) if med[n]["cp"] and med[n]["cp"] > 0 else np.nan
            for n in xs
        ]
        ax.plot(xs, frac, fmt, color=color, lw=2, ms=5, label=label)
    ax.axhline(0.5, color="#C62828", ls="--", lw=1.2, label="50% crossover")
    ax.annotate("orchestration dominates →", xy=(16, 0.85), fontsize=7, color="#455A64")
    log_n_axis(ax, POW2_FULL)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=6)

    fig.suptitle(
        "Descriptor scaling — analytical panel (9 views) · Spot low/medium · D=10k–50k",
        fontsize=13,
        y=0.995,
    )

    out_png = REPO / "tmp" / "probe_analysis_panel.png"
    fig.savefig(out_png, bbox_inches="tight", facecolor=BG)
    print(out_png)

    # ── Extra figure: medium decomposition + speedup ─────────────────────
    fig2, axes = plt.subplots(1, 3, figsize=(14, 4.2), dpi=130)
    fig2.patch.set_facecolor(BG)

    # J: medium decomposition
    ax = axes[0]
    style_ax(ax, "J · D=50k Spot medium — compute vs sched", ylabel="seconds")
    xs = [n for n in POW2_FULL if n in spot_med]
    ax.bar(np.arange(len(xs)) - 0.175, [spot_med[n]["comp"] for n in xs], 0.35, color="#FFCC80", label="computation")
    ax.bar(np.arange(len(xs)) + 0.175, [spot_med[n]["sched"] for n in xs], 0.35, color="#E65100", label="scheduling")
    ax.set_xticks(np.arange(len(xs)))
    ax.set_xticklabels(xs)
    ax.legend(frameon=False, fontsize=7)

    # K: Ideal vs actual speedup (Spot low D=50k)
    ax = axes[1]
    style_ax(ax, "K · Speedup vs N (Spot low D=50k)", ylabel="speedup vs N=2")
    if 2 in spot_low:
        t2 = spot_low[2]["comp"]
        xs = [n for n in POW2_FULL if n in spot_low]
        ideal = [n / 2 for n in xs]
        actual = [t2 / spot_low[n]["comp"] if spot_low[n]["comp"] > 0 else np.nan for n in xs]
        ax.plot(xs, ideal, ":", color="#90A4AE", lw=2, label="ideal (comp)")
        ax.plot(xs, actual, "o-", color="#2E7D32", lw=2, ms=5, label="actual (comp)")
        # wall-clock speedup (usually poor)
        t2_cp = spot_low[2]["cp"]
        wall = [t2_cp / spot_low[n]["cp"] if spot_low[n]["cp"] > 0 else np.nan for n in xs]
        ax.plot(xs, wall, "s--", color="#C62828", lw=2, ms=5, label="wall (cluster_parallel)")
        log_n_axis(ax, POW2_FULL)
        ax.legend(frameon=False, fontsize=7)

    # L: Cost at N* by D
    ax = axes[2]
    style_ax(ax, "L · Cost at N* vs D (Spot low)", ylabel="cost (USD)", xlabel="Dataset size D")
    costs_star = []
    for d in ds_plot:
        opt = find_min(d_med_map[d])
        costs_star.append(opt["cost"] if opt else np.nan)
    ax.bar([str(d // 1000) + "k" for d in ds_plot], costs_star, color="#00897B", width=0.55)
    for i, (d, c) in enumerate(zip(ds_plot, costs_star)):
        opt = find_min(d_med_map[d])
        if opt:
            ax.annotate(f"N={opt['N']}", (i, c), ha="center", va="bottom", fontsize=7)

    fig2.suptitle("Extra analytical views — decomposition, speedup, cost", fontsize=11)
    plt.tight_layout()
    out2 = REPO / "tmp" / "probe_analysis_panel_extra.png"
    fig2.savefig(out2, bbox_inches="tight", facecolor=BG)
    print(out2)

    # Keep classic decomposition too
    fig3, axes3 = plt.subplots(1, 2, figsize=(12, 4.5), dpi=130)
    fig3.patch.set_facecolor(BG)
    for ax, med, title, c_comp, c_sched in [
        (axes3[0], spot_low, "Spot low D=50k", "#81C784", "#2E7D32"),
        (axes3[1], spot_med, "Spot medium D=50k", "#FFCC80", "#E65100"),
    ]:
        ax.set_facecolor(BG)
        xs = [n for n in POW2_FULL if n in med]
        ax.bar(xs, [med[n]["comp"] for n in xs], width=1.5, color=c_comp, label="computation", alpha=0.9)
        ax.bar(xs, [med[n]["sched"] for n in xs], width=1.5, bottom=[med[n]["comp"] for n in xs], color=c_sched, label="scheduling", alpha=0.7)
        log_n_axis(ax, xs)
        ax.set_xlabel("N")
        ax.set_ylabel("seconds")
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=8)
        ax.grid(True, axis="y", alpha=0.3, color=GRID)
    fig3.suptitle("Wall time decomposition — compute vs scheduling stagger", fontsize=11)
    plt.tight_layout()
    out3 = REPO / "tmp" / "probe_analysis_decomposition.png"
    fig3.savefig(out3, bbox_inches="tight", facecolor=BG)
    print(out3)

    # Summary JSON
    summary = {
        "optima": {
            "spot_low_d50k": find_min(spot_low),
            "spot_med_d50k": find_min(spot_med),
            "spot_low_d20k": find_min(d20k_low),
            "spot_low_d40k": find_min(d40k_low),
            "spot_med_d20k": find_min(d20k_med),
            "spot_med_d40k": find_min(d40k_med),
            "od_low_d50k": find_min(od_low),
            "od_med_d50k": find_min(od_med),
            "spot_d10k": find_min(d10k),
        },
        "nstar_vs_D_spot_low": {
            str(d): find_min(d_med_map[d]) for d in MULTI_D if d in d_med_map and d_med_map[d]
        },
        "nstar_vs_D_spot_medium": {
            str(d): find_min(d_med_map_med[d]) for d in d_med_map_med if d_med_map_med[d]
        },
        "paper_nstar": PAPER_NSTAR,
        "fitted_vertices": {
            "local_1d": {
                str(d): local_fits.get(d) for d in ds_plot
            },
            "global_TN_D": {
                "coefficients": {k: global_fit.get(k) for k in ("a", "b", "c", "d", "e", "r2")}
                if global_fit.get("ok")
                else None,
                "Nstar_raw": {str(k): v for k, v in global_fit.get("nstar_raw", {}).items()}
                if global_fit.get("ok")
                else None,
            },
            "note": (
                "Do NOT publish discrete pow2 argmin as N*(D). "
                "Prefer global T(N,D) fitted vertex or per-D quadratic when γ>0. "
                "Flat argmin=16 across D=20–50k is a sampling-grid artifact."
            ),
        },
        "anomalies_pending_5rep": {
            "d50k_spot_low_N32": {
                "reason": "scheduling spike (sched≈173s, comp≈12s) — single/2-rep outlier",
                "config": "experiments/configs/confirm_d50k_n32_spot_low.yaml",
            },
            "d20k_spot_medium_N8": {
                "reason": "scheduling spike (sched≈120s, comp≈37s) — not compute blowup",
                "config": "experiments/configs/confirm_d20k_n8_spot_medium.yaml",
            },
        },
        "overnight_n25_d50k_cp": ov50.get(25, {}).get("cp"),
        "figures": {
            "main_9panel": "tmp/probe_analysis_panel.png",
            "extra_3panel": "tmp/probe_analysis_panel_extra.png",
            "decomposition": "tmp/probe_analysis_decomposition.png",
            "summary_json": "tmp/probe_analysis_summary.json",
            "conclusions_md": "tmp/probe_analysis_conclusions.md",
            "nstar_math_md": "tmp/nstar_math_analysis.md",
        },
        "series": {
            k: {str(n): v for n, v in m.items()}
            for k, m in [
                ("spot_low_d50k", spot_low),
                ("spot_med_d50k", spot_med),
                ("spot_low_d20k", d20k_low),
                ("spot_low_d40k", d40k_low),
                ("spot_med_d20k", d20k_med),
                ("spot_med_d40k", d40k_med),
                ("od_low_d50k", od_low),
                ("od_med_d50k", od_med),
                ("d10k", d10k),
            ]
        },
    }
    out_json = REPO / "tmp" / "probe_analysis_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(out_json)
    # Narrative conclusions live in tmp/probe_analysis_conclusions.md (hand-maintained;
    # do not overwrite — corrected 2026-07-16 to reject discrete-argmin plateau claim).
    print("Narrative summary: tmp/probe_analysis_conclusions.md")
    print("Fitted vertices:   tmp/nstar_fitted_vertices.json")


if __name__ == "__main__":
    main()
