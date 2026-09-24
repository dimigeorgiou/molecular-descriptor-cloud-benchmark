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


@dataclass
class ModelCoefficients:
    """Fitted coefficients for T(N,D) = a + bN + cD + dN² + eND"""
    a: float = 500.0   # baseline overhead
    b: float = -8.0    # linear node benefit
    c: float = 0.008   # data size cost
    d: float = 0.05    # quadratic overhead (parallelism penalty)
    e: float = 0.00002 # interaction: dataset × nodes

    # metadata
    r_squared: Optional[float] = None
    fitted_from_n_samples: Optional[int] = None
    source: str = "paper_estimates"  # "paper_estimates" | "fitted"

    def predict(self, n_nodes: int, dataset_size: int) -> float:
        """
        Predict execution time in seconds.

        T(N, D) = a + bN + cD + dN² + eND

        Args:
            n_nodes: Number of cluster nodes
            dataset_size: Number of chemical compounds

        Returns:
            Predicted execution time in seconds
        """
        N, D = float(n_nodes), float(dataset_size)
        return self.a + self.b * N + self.c * D + self.d * N**2 + self.e * N * D

    def optimal_nodes(
        self,
        dataset_size: int,
        n_min: int = 1,
        n_max: int = 200
    ) -> int:
        """
        Analytically compute N*(D) = -(b + eD) / (2d).

        From paper Section 5: derivative dT/dN = b + 2dN + eD = 0
        → N*(D) = -(b + eD) / (2d)

        Since d > 0, the function is convex → this is a global minimum.

        Args:
            dataset_size: Number of compounds D
            n_min: Minimum allowed nodes (infra constraint)
            n_max: Maximum allowed nodes (infra constraint)

        Returns:
            Optimal integer node count, clamped to [n_min, n_max]
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
        n_max: int = 200
    ) -> dict[int, dict]:
        """Return optimal nodes and predicted time for a list of dataset sizes."""
        results = {}
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
        """Load from JSON."""
        with open(path) as f:
            data = json.load(f)
        model = cls(**data)
        logger.info(f"Loaded model from {path} (R²={model.r_squared})")
        return model


def fit_model(experiment_results: list[dict]) -> ModelCoefficients:
    """
    Fit T(N,D) = a + bN + cD + dN² + eND via OLS regression.

    Args:
        experiment_results: list of dicts with keys:
            - n_nodes: int
            - dataset_size: int
            - execution_time: float (seconds)

    Returns:
        Fitted ModelCoefficients with R² score
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score

    if len(experiment_results) < 5:
        raise ValueError(f"Need at least 5 data points to fit model, got {len(experiment_results)}")

    rows = []
    y = []
    for r in experiment_results:
        N = float(r["n_nodes"])
        D = float(r["dataset_size"])
        rows.append([N, D, N**2, N * D])
        y.append(float(r["execution_time"]))

    X = np.array(rows)
    y = np.array(y)

    reg = LinearRegression().fit(X, y)
    y_pred = reg.predict(X)
    r2 = r2_score(y, y_pred)

    b, c, d, e = reg.coef_
    a = reg.intercept_

    logger.info(f"Fitted model: a={a:.3f}, b={b:.3f}, c={c:.6f}, d={d:.6f}, e={e:.8f}")
    logger.info(f"R² = {r2:.4f} (n={len(y)} observations)")

    if d <= 0:
        logger.warning("⚠️ Fitted d ≤ 0 — model not convex. Check your data!")

    return ModelCoefficients(
        a=float(a), b=float(b), c=float(c), d=float(d), e=float(e),
        r_squared=float(r2),
        fitted_from_n_samples=len(y),
        source="fitted"
    )


def load_results_for_fitting(results_dir: Path) -> list[dict]:
    """Load all experiment result JSON files from directory."""
    results = []
    for fp in sorted(results_dir.glob("*.json")):
        if "estimate" in fp.name:
            continue
        with open(fp) as f:
            data = json.load(f)
        # Support both single result and list of results
        if isinstance(data, list):
            results.extend(data)
        elif "runs" in data:
            results.extend(data["runs"])
        else:
            results.append(data)
    logger.info(f"Loaded {len(results)} data points from {results_dir}")
    return results


if __name__ == "__main__":
    import sys

    # CLI: python src/core/model.py fit --results-dir experiments/results/
    # CLI: python src/core/model.py optimal-table --model fitted_model.json --sizes 5000 10000 50000
    if len(sys.argv) < 2:
        print("Usage: python model.py [fit|optimal-table|predict] [options]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "fit":
        results_dir = Path("experiments/results")
        results = load_results_for_fitting(results_dir)
        model = fit_model(results)
        out = Path("experiments/results/fitted_model.json")
        model.save(out)
        print(f"\nFitted model saved to {out}")
        print(f"R² = {model.r_squared:.4f}")

    elif cmd == "optimal-table":
        model_path = Path("experiments/results/fitted_model.json")
        if model_path.exists():
            model = ModelCoefficients.load(model_path)
        else:
            logger.warning("No fitted model found, using paper estimates")
            model = ModelCoefficients()

        sizes = [5000, 10000, 20000, 30000, 40000, 50000]
        table = model.optimal_nodes_table(sizes)
        print(f"\n{'Dataset Size':>15} {'Optimal Nodes':>15} {'Predicted Time (s)':>20}")
        print("-" * 55)
        for D, v in table.items():
            print(f"{D:>15,} {v['optimal_nodes']:>15} {v['predicted_time_sec']:>20.1f}")

    elif cmd == "predict":
        n = int(sys.argv[2])
        d = int(sys.argv[3])
        model = ModelCoefficients()
        t = model.predict(n, d)
        print(f"T(N={n}, D={d}) = {t:.1f}s")
