#!/usr/bin/env python3
"""Build data/paper_execution_times.json from PDF Table 1 & 2 (page 4 transcription)."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "paper_execution_times.json"

# Transcribed from:
# docs/Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics.docx.pdf
# page 4 — Table 1 (5K–25K) and Table 2 (30K–50K), N ∈ {25,35,...,185}

NODE_CONFIGS = list(range(25, 186, 10))

TABLE1: dict[int, list[float]] = {
    5000: [169.55, 171.38, 170.92, 151.84, 133.91, 130.62, 134.0, 137.81, 142.98, 147.65, 152.56, 154.38, 140.89, 146.92, 145.26, 149.1, 159.8],
    10000: [211.74, 212.75, 211.78, 199.87, 187.78, 165.74, 155.7, 158.37, 155.15, 155.93, 152.81, 153.03, 152.2, 161.05, 170.19, 170.79, 170.61],
    15000: [371.77, 288.31, 209.89, 200.64, 180.44, 183.49, 215.73, 189.36, 176.36, 179.09, 198.74, 193.77, 184.07, 186.25, 178.08, 176.77, 178.14],
    20000: [476.84, 288.19, 250.09, 239.43, 238.09, 236.41, 238.37, 217.29, 198.76, 195.91, 192.62, 187.45, 183.19, 201.25, 211.94, 216.76, 220.62],
    25000: [568.92, 397.3, 382.3, 296.24, 251.37, 250.26, 254.56, 255.59, 253.42, 253.2, 242.59, 236.16, 228.92, 229.86, 222.94, 214.26, 212.91],
}

TABLE2: dict[int, list[float]] = {
    30000: [469.3, 467.2, 458.55, 389.11, 362.46, 290.99, 259.93, 256.14, 246.72, 249.75, 249.03, 251.47, 248.68, 253.3, 242.96, 242.88, 245.25],
    35000: [829.06, 533.0, 361.52, 358.62, 355.71, 314.75, 297.48, 295.27, 269.87, 269.88, 265.58, 265.41, 263.3, 258.86, 239.73, 239.73, 239.94],
    40000: [607.89, 500.8, 395.54, 389.12, 386.91, 368.41, 307.4, 295.36, 280.3, 279.59, 263.56, 360.07, 251.3, 256.22, 253.36, 253.56, 256.17],
    45000: [1043.0, 637.9, 414.51, 413.23, 408.91, 407.4, 409.1, 396.36, 378.58, 378.69, 382.69, 315.47, 297.45, 313.12, 337.2, 332.46, 332.04],
    50000: [794.42, 706.5, 681.63, 580.6, 435.98, 429.4, 383.37, 357.57, 349.17, 343.35, 328.69, 319.07, 315.45, 319.97, 315.7, 309.42, 307.57],
}


def _rows_from_table(table: dict[int, list[float]], table_name: str) -> list[dict]:
    rows: list[dict] = []
    for d, times in table.items():
        if len(times) != len(NODE_CONFIGS):
            raise ValueError(f"{table_name} D={d}: expected {len(NODE_CONFIGS)} times, got {len(times)}")
        for n, t in zip(NODE_CONFIGS, times):
            rows.append({"dataset_size": d, "n_nodes": n, "execution_time": float(t), "table": table_name})
    return rows


def main() -> None:
    rows = _rows_from_table(TABLE1, "table_1") + _rows_from_table(TABLE2, "table_2")
    payload = {
        "source_document": "Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics (2025)",
        "pdf_path": "docs/Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics.docx.pdf",
        "pdf_page": 4,
        "provenance": "paper_pdf_table_transcription",
        "metric": "execution_time_sec",
        "description": "End-to-end execution time including cluster formation, scheduling, distribution, communication, synchronization, and descriptor calculation (paper Table 1 & 2).",
        "node_configs": NODE_CONFIGS,
        "table_1_dataset_sizes": sorted(TABLE1.keys()),
        "table_2_dataset_sizes": sorted(TABLE2.keys()),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(rows)} rows → {OUT}")


if __name__ == "__main__":
    main()
