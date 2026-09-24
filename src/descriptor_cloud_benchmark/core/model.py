"""
Performance model T(N,D) = a + bN + cD + dN² + eND
Based on: "Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics"
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PAPER_EXECUTION_TIMES_PATH = _REPO_ROOT / "data" / "paper_execution_times.json"
# Legacy path — must NOT be used for paper_fitted (was Spot replication data).
_PAPER_TABLE1_PATH = _REPO_ROOT / "data" / "paper_table1_execution_times.json"
_PAPER_FITTED_PATH = _REPO_ROOT / "data" / "paper_fitted_model.json"

_EXPECTED_PAPER_NODE_CONFIGS = list(range(25, 186, 10))
_EXPECTED_PAPER_TABLE1_D = [5000, 10000, 15000, 20000, 25000]
_EXPECTED_PAPER_TABLE2_D = [30000, 35000, 40000, 45000, 50000]
_EXPECTED_PAPER_ROW_COUNT = len(_EXPECTED_PAPER_NODE_CONFIGS) * (
    len(_EXPECTED_PAPER_TABLE1_D) + len(_EXPECTED_PAPER_TABLE2_D)
)
_VALID_PAPER_PROVENANCE = frozenset(
    {"paper_pdf_table_transcription", "paper_pdf_page4_transcription"}
)
_INVALID_PAPER_PROVENANCE_MARKERS = (
    "replication",
    "spot",
    "2026-05",
    "batch_full_pipeline",
    "pending pdf",
)


@dataclass
class ModelCoefficients:
    """Fitted coefficients for T(N,D) = a + bN + cD + dN² + eND."""

    a: float = 500.0
    b: float = -8.0
    c: float = 0.008
    d: float = 0.05
    e: float = 0.00002

    # metadata
    r_squared: Optional[float] = None
    fitted_from_n_samples: Optional[int] = None
    source: str = "paper_estimates"

    def __post_init__(self) -> None:
        if self.source == "paper_estimates":
            logger.debug(
                "ModelCoefficients with source=paper_estimates are PLACEHOLDER defaults, "
                "not fit to paper Table 1 — use paper_fitted() or load_paper_fitted()."
            )

    @classmethod
    def placeholder_defaults(cls) -> "ModelCoefficients":
        """
        Hand-tuned starting guesses for the estimator — NOT fit to paper data.

        Do not cite these as ground truth or paper-reported coefficients.
        """
        return cls(
            a=500.0,
            b=-8.0,
            c=0.008,
            d=0.05,
            e=0.00002,
            source="paper_estimates",
        )

    def predict(self, n_nodes: int, dataset_size: int) -> float:
        """
        Predict execution time in seconds.

        T(N, D) = a + bN + cD + dN² + eND
        """
        N, D = float(n_nodes), float(dataset_size)
        return self.a + self.b * N + self.c * D + self.d * N**2 + self.e * N * D

    def optimal_nodes(
        self,
        dataset_size: int,
        n_min: int = 1,
        n_max: int = 200,
    ) -> int:
        """
        Analytically compute N*(D) = -(b + eD) / (2d).

        From paper Section 5: derivative dT/dN = b + 2dN + eD = 0
        → N*(D) = -(b + eD) / (2d)
        """
        D = float(dataset_size)
        if self.d <= 0:
            logger.warning("d ≤ 0: model not convex, returning n_max")
            return n_max
        n_star = -(self.b + self.e * D) / (2 * self.d)
        clamped = int(np.clip(round(n_star), n_min, n_max))
        logger.debug(f"N*(D={dataset_size}) = {n_star:.1f} → {clamped} (clamped)")
        return clamped

    def optimal_nodes_table(
        self,
        dataset_sizes: list[int],
        n_min: int = 1,
        n_max: int = 200,
    ) -> dict[int, dict]:
        """Return optimal nodes and predicted time for a list of dataset sizes."""
        results: dict[int, dict] = {}
        for D in dataset_sizes:
            N_opt = self.optimal_nodes(D, n_min, n_max)
            t_opt = self.predict(N_opt, D)
            results[D] = {
                "optimal_nodes": N_opt,
                "predicted_time_sec": round(t_opt, 1),
            }
        return results

    def save(self, path: Path) -> None:
        """Save coefficients to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)
        logger.success(f"Model saved → {path}")

    @classmethod
    def load(cls, path: Path) -> "ModelCoefficients":
        """Load coefficients from JSON."""
        with open(path) as f:
            data = json.load(f)
        model = cls(**data)
        logger.info(f"Loaded model from {path} (source={model.source}, R²={model.r_squared})")
        return model


def _validate_paper_execution_payload(payload: dict, fp: Path) -> None:
    """Reject replication/Spot data masquerading as paper Table 1/2."""
    provenance = str(payload.get("provenance", "")).lower()
    if provenance and provenance not in _VALID_PAPER_PROVENANCE:
        raise ValueError(
            f"Invalid provenance in {fp}: {payload.get('provenance')!r}. "
            f"Expected one of {sorted(_VALID_PAPER_PROVENANCE)} (PDF transcription)."
        )
    for marker in _INVALID_PAPER_PROVENANCE_MARKERS:
        if marker in provenance:
            raise ValueError(
                f"Refusing paper fit: {fp} provenance looks like replication data "
                f"({payload.get('provenance')!r}), not paper PDF tables."
            )

    rows = payload.get("rows", [])
    if len(rows) != _EXPECTED_PAPER_ROW_COUNT:
        raise ValueError(
            f"Expected {_EXPECTED_PAPER_ROW_COUNT} paper rows in {fp}, got {len(rows)}. "
            "Regenerate via scripts/build_paper_execution_times_from_pdf.py."
        )

    seen: set[tuple[int, int]] = set()
    for row in rows:
        n = int(row["n_nodes"])
        d = int(row["dataset_size"])
        if n not in _EXPECTED_PAPER_NODE_CONFIGS:
            raise ValueError(f"Unexpected n_nodes={n} in {fp} (paper uses 25–185 step 10).")
        if d not in _EXPECTED_PAPER_TABLE1_D + _EXPECTED_PAPER_TABLE2_D:
            raise ValueError(f"Unexpected dataset_size={d} in {fp}.")
        key = (d, n)
        if key in seen:
            raise ValueError(f"Duplicate (D,N)=({d},{n}) in {fp}.")
        seen.add(key)


def load_paper_execution_rows(path: Path | None = None) -> list[dict]:
    """Load paper Table 1+2 execution-time grid transcribed from the PDF."""
    fp = path or _PAPER_EXECUTION_TIMES_PATH
    if not fp.is_file():
        raise FileNotFoundError(
            f"Paper execution data not found at {fp}. "
            "Run: python scripts/build_paper_execution_times_from_pdf.py"
        )
    with open(fp) as f:
        payload = json.load(f)
    _validate_paper_execution_payload(payload, fp)
    rows = payload["rows"]
    normalized: list[dict] = []
    for row in rows:
        normalized.append(
            {
                "n_nodes": int(row["n_nodes"]),
                "dataset_size": int(row["dataset_size"]),
                "execution_time": float(row["execution_time"]),
            }
        )
    logger.info(
        "Loaded {} paper Table 1+2 rows from {} (provenance={})",
        len(normalized),
        fp,
        payload.get("provenance"),
    )
    return normalized


def load_paper_table1_rows(path: Path | None = None) -> list[dict]:
    """Backward-compatible alias — loads full paper Table 1+2 grid."""
    if path is None:
        if _PAPER_TABLE1_PATH.is_file() and not _PAPER_EXECUTION_TIMES_PATH.is_file():
            raise ValueError(
                f"Legacy {_PAPER_TABLE1_PATH.name} must not be used for paper_fitted "
                f"(it was Spot replication data). Use {_PAPER_EXECUTION_TIMES_PATH.name} "
                "from PDF transcription instead."
            )
        return load_paper_execution_rows(_PAPER_EXECUTION_TIMES_PATH)
    return load_paper_execution_rows(path)


def fit_paper_table1_model(path: Path | None = None) -> ModelCoefficients:
    """Fit T(N,D) to paper Table 1+2 and return source=paper_fitted coefficients."""
    rows = load_paper_execution_rows(path)
    model = fit_model(rows)
    model.source = "paper_fitted"
    if model.r_squared is not None and model.r_squared < 0.5:
        logger.warning(
            "paper_fitted R²={:.4f} is low — verify PDF transcription, not replication JSON",
            model.r_squared,
        )
    return model


def load_paper_fitted(path: Path | None = None, *, refit: bool = False) -> ModelCoefficients:
    """Load cached paper_fitted coefficients or fit from paper Table 1+2 and cache."""
    fp = path or _PAPER_FITTED_PATH
    if fp.is_file() and not refit:
        model = ModelCoefficients.load(fp)
        if model.source != "paper_fitted":
            logger.warning(
                "Cached model at {} has source={}; refitting from paper tables",
                fp,
                model.source,
            )
        elif model.r_squared is not None and model.r_squared < 0.5:
            logger.warning(
                "Cached paper_fitted R²={:.4f} is suspect; refitting from paper tables",
                model.r_squared,
            )
        else:
            return model
    model = fit_paper_table1_model()
    model.save(fp)
    return model


def fit_model(experiment_results: list[dict]) -> ModelCoefficients:
    """
    Fit T(N,D) = a + bN + cD + dN² + eND via OLS regression.

    experiment_results: list of dicts with keys:
        - n_nodes: int
        - dataset_size: int
        - execution_time: float (seconds)
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score

    if len(experiment_results) < 5:
        raise ValueError(
            f"Need at least 5 data points to fit model, got {len(experiment_results)}"
        )

    rows: list[list[float]] = []
    y: list[float] = []
    for r in experiment_results:
        N = float(r["n_nodes"])
        D = float(r["dataset_size"])
        rows.append([N, D, N**2, N * D])
        y.append(float(r["execution_time"]))

    X = np.array(rows)
    y_arr = np.array(y)

    reg = LinearRegression().fit(X, y_arr)
    y_pred = reg.predict(X)
    r2 = r2_score(y_arr, y_pred)

    b, c, d, e = reg.coef_
    a = reg.intercept_

    logger.info(
        "Fitted model: a={:.3f}, b={:.3f}, c={:.6f}, d={:.6f}, e={:.8f}",
        a,
        b,
        c,
        d,
        e,
    )
    logger.info("R² = {:.4f} (n={} observations)", r2, len(y_arr))

    if d <= 0:
        logger.warning("⚠️ Fitted d ≤ 0 — model not convex. Check your data!")

    return ModelCoefficients(
        a=float(a),
        b=float(b),
        c=float(c),
        d=float(d),
        e=float(e),
        r_squared=float(r2),
        fitted_from_n_samples=len(y_arr),
        source="fitted",
    )


def load_results_for_fitting(results_dir: Path) -> list[dict]:
    """Load all experiment result JSON files from a directory."""
    results: list[dict] = []
    for fp in sorted(results_dir.glob("*.json")):
        if "estimate" in fp.name or "fitted_model" in fp.name:
            continue
        with open(fp) as f:
            data = json.load(f)
        if isinstance(data, list):
            results.extend(data)
        elif isinstance(data, dict) and "runs" in data:
            results.extend(data["runs"])
        elif isinstance(data, dict) and {"n_nodes", "dataset_size", "execution_time"} <= data.keys():
            results.append(data)
    logger.info("Loaded {} data points from {}", len(results), results_dir)
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python src/core/model.py [fit|fit-paper|optimal-table|predict] ...")
        raise SystemExit(1)

    cmd = sys.argv[1]

    if cmd == "fit":
        results_dir = Path("experiments/results")
        results = load_results_for_fitting(results_dir)
        model = fit_model(results)
        out = Path("experiments/results/fitted_model.json")
        model.save(out)
        print(f"\nFitted model saved to {out}")
        print(f"R² = {model.r_squared:.4f}")

    elif cmd == "fit-paper":
        model = fit_paper_table1_model()
        model.save(_PAPER_FITTED_PATH)
        print(f"\nPaper-fitted model saved to {_PAPER_FITTED_PATH}")
        print(f"R² = {model.r_squared:.4f} (n={model.fitted_from_n_samples})")
        print(
            f"Coefficients: a={model.a:.3f} b={model.b:.3f} c={model.c:.6f} "
            f"d={model.d:.6f} e={model.e:.8f}"
        )

    elif cmd == "optimal-table":
        model_path = Path("experiments/results/fitted_model.json")
        if model_path.exists():
            model = ModelCoefficients.load(model_path)
        else:
            try:
                model = load_paper_fitted()
                logger.info("Using paper_fitted model for optimal-table")
            except FileNotFoundError:
                logger.warning("No fitted model found, using placeholder defaults")
                model = ModelCoefficients.placeholder_defaults()

        sizes = [5000, 10000, 20000, 30000, 40000, 50000]
        table = model.optimal_nodes_table(sizes)
        print(f"\n{'Dataset Size':>15} {'Optimal Nodes':>15} {'Predicted Time (s)':>20}")
        print("-" * 55)
        for D, v in table.items():
            print(f"{D:>15,} {v['optimal_nodes']:>15} {v['predicted_time_sec']:>20.1f}")

    elif cmd == "predict":
        n = int(sys.argv[2])
        d = int(sys.argv[3])
        try:
            model = load_paper_fitted()
        except FileNotFoundError:
            model = ModelCoefficients.placeholder_defaults()
        t = model.predict(n, d)
        print(f"T(N={n}, D={d}) = {t:.1f}s (source={model.source})")

    else:
        print(f"Unknown command: {cmd}")
        raise SystemExit(1)
