"""
Experiment timing utilities.

Provides a context-manager-based timer that can track named phases with
millisecond precision and export a flat dict ready for Google Sheets.

Usage:
    from descriptor_cloud_benchmark.core.timer import ExperimentTimer

    with ExperimentTimer() as t:
        with t.phase("s3_upload_sec"):
            upload_to_s3(...)
        with t.phase("computation_sec"):
            run_descriptors(...)
    timings = t.to_dict()
"""
from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from typing import Dict, Iterator, Optional


_PHASE_KEYS = {
    "s3_upload_sec",
    "cluster_init_sec",
    "scheduling_sec",
    "computation_sec",
    "sync_overhead_sec",
    "result_upload_sec",
    "total_pipeline_sec",
}


@dataclass
class ExperimentTimer:
    """
    High-level timing helper for experiments.

    Times named phases in seconds (float) and stores additional metadata
    such as dataset_size_mb and SMILES statistics.
    """

    _phase_times: Dict[str, float] = field(default_factory=dict)
    _t0: float = field(default_factory=time.perf_counter)

    # Optional metadata fields that callers can populate
    dataset_size_mb: Optional[float] = None
    smiles_avg_length: Optional[float] = None
    smiles_complexity: Optional[str] = None  # "low" | "medium" | "high"

    def __enter__(self) -> "ExperimentTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        # If total_pipeline_sec was not explicitly recorded as a phase,
        # compute it automatically as wall-clock time from __enter__.
        if "total_pipeline_sec" not in self._phase_times:
            elapsed = time.perf_counter() - self._t0
            self._phase_times["total_pipeline_sec"] = round(elapsed, 3)

    @contextlib.contextmanager
    def phase(self, key: str) -> Iterator[None]:
        """
        Context manager for timing a named phase.

        Example:
            with timer.phase("computation_sec"):
                run_descriptors(...)
        """
        if key not in _PHASE_KEYS:
            # Allow arbitrary keys but keep known set explicit for clarity.
            # We still record any custom key the caller passes.
            pass

        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            duration = round(end - start, 3)
            # If called multiple times for the same key, accumulate.
            self._phase_times[key] = self._phase_times.get(key, 0.0) + duration

    def set_metadata(
        self,
        *,
        dataset_size_mb: Optional[float] = None,
        smiles_avg_length: Optional[float] = None,
        smiles_complexity: Optional[str] = None,
    ) -> None:
        """
        Convenience helper to attach common metadata fields.
        """
        if dataset_size_mb is not None:
            self.dataset_size_mb = float(dataset_size_mb)
        if smiles_avg_length is not None:
            self.smiles_avg_length = float(smiles_avg_length)
        if smiles_complexity is not None:
            self.smiles_complexity = smiles_complexity

    def to_dict(self) -> Dict[str, float | str]:
        """
        Export a flat dict suitable for JSON serialization and Sheets logging.

        All known timing keys are present; missing ones default to 0.0.
        Metadata fields are included when available, otherwise omitted.
        """
        data: Dict[str, float | str] = {}

        # Ensure all known phase keys exist (even if zero)
        for key in sorted(_PHASE_KEYS):
            data[key] = round(float(self._phase_times.get(key, 0.0)), 3)

        if self.dataset_size_mb is not None:
            data["dataset_size_mb"] = round(float(self.dataset_size_mb), 3)
        if self.smiles_avg_length is not None:
            data["smiles_avg_length"] = round(float(self.smiles_avg_length), 3)
        if self.smiles_complexity is not None:
            data["smiles_complexity"] = self.smiles_complexity

        return data


__all__ = ["ExperimentTimer"]

