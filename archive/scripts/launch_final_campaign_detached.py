#!/usr/bin/env python3
"""
Detach final-campaign experiment runners (macOS-safe start_new_session).

Usage:
  python scripts/launch_final_campaign_detached.py 1
  python scripts/launch_final_campaign_detached.py 2 3 4 8
  python scripts/launch_final_campaign_detached.py all
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CFG_DIR = REPO / "experiments/configs/final"
LOGROOT = REPO / "tmp/final_campaign"
PY = os.environ.get(
    "PY", "/opt/anaconda3/envs/venv_chemoinformatics/bin/python"
)

WAVES: dict[int, list[str]] = {
    1: [
        "final_w1_d5k_n128_od_low",
        "final_w1_d5k_n128_od_medium",
        "final_w1_d10k_n128_od_medium",
    ],
    2: ["final_w2_d10k_pow2_spot_low"],
    3: [
        "final_w3_d50k_pow2_spot_low",
        "final_w3_d50k_pow2_spot_medium",
    ],
    4: [
        "final_w4_d20k_pow2_spot_low_rep2",
        "final_w4_d20k_pow2_spot_medium_rep2",
        "final_w4_d40k_pow2_spot_low_rep2",
        "final_w4_d40k_pow2_spot_medium_rep2",
    ],
    5: [
        "final_w5_d5k_pow2_spot_high",
        "final_w5_d20k_pow2_spot_high",
        "final_w5_d40k_pow2_spot_high",
    ],
    6: [
        "final_w6_d100k_pow2_spot_low",
        "final_w6_d100k_pow2_spot_medium",
    ],
    7: [
        "final_w7_d100k_pow2_od_low",
        "final_w7_d100k_pow2_od_medium",
    ],
    8: [
        "final_w8_d20k_midn_spot_low",
        "final_w8_d20k_midn_spot_medium",
        "final_w8_d40k_midn_spot_low",
        "final_w8_d40k_midn_spot_medium",
    ],
    9: [
        "final_w9_d5k_n150_185_spot_low",
        "final_w9_d5k_n150_185_spot_medium",
    ],
}

PREREQ_FILES: dict[int, list[str]] = {
    5: [
        "datasets/samples/smiles_5000_high.csv",
        "datasets/samples/smiles_20000_high.csv",
        "datasets/samples/smiles_40000_high.csv",
    ],
    6: [
        "datasets/samples/smiles_100000_low.csv",
        "datasets/samples/smiles_100000_medium.csv",
    ],
    7: [
        "datasets/samples/smiles_100000_low.csv",
        "datasets/samples/smiles_100000_medium.csv",
    ],
}


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


def _check_prereq(wave: int) -> None:
    for rel in PREREQ_FILES.get(wave, []):
        p = REPO / rel
        if not p.is_file():
            raise SystemExit(f"Missing {rel} (needed for wave {wave})")


def launch_wave(wave: int, stagger_sec: float = 8.0) -> list[int]:
    _check_prereq(wave)
    names = WAVES[wave]
    logdir = LOGROOT / f"wave_{wave}"
    logdir.mkdir(parents=True, exist_ok=True)
    master = logdir / "master.log"
    pids: list[int] = []

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["SKIP_PRE_RUN_ESTIMATE"] = "1"
    env.setdefault("BATCH_RUNNING_DEADLINE_SEC", "900")
    if wave == 9:
        env["BATCH_RETRY_ATTEMPTS"] = "4"

    with master.open("a") as mf:
        mf.write(f"\n=== WAVE {wave} LAUNCH {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n")
        for name in names:
            cfg = CFG_DIR / f"{name}.yaml"
            if not cfg.is_file():
                raise SystemExit(f"Missing config {cfg}")
            log = LOGROOT / f"w{wave}_{name}.log"
            cmd = [PY, str(REPO / "experiments/run_experiment.py"), "--config", str(cfg)]
            with log.open("w") as lf:
                lf.write(f"START {name} wave={wave}\n")
            proc = subprocess.Popen(
                cmd,
                cwd=str(REPO),
                env=env,
                stdout=open(log, "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            pids.append(proc.pid)
            msg = f"LAUNCH {name} pid={proc.pid} log={log}\n"
            print(msg, end="")
            mf.write(msg)
            time.sleep(stagger_sec)
        (logdir / "pids.txt").write_text(" ".join(str(p) for p in pids) + "\n")
        mf.write(f"PIDS: {' '.join(map(str, pids))}\n")
    return pids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "waves",
        nargs="+",
        help="Wave ids or 'all'",
    )
    parser.add_argument("--stagger", type=float, default=8.0)
    args = parser.parse_args()
    _load_dotenv()
    LOGROOT.mkdir(parents=True, exist_ok=True)

    if not (CFG_DIR / "final_w1_d5k_n128_od_low.yaml").is_file():
        subprocess.check_call(
            [PY, str(REPO / "scripts/generate_final_campaign_configs.py")],
            cwd=str(REPO),
        )

    if args.waves == ["all"]:
        # Datasets-dependent waves last; mid-N/rep before huge D=50k/100k
        wave_ids = [1, 2, 4, 8, 3, 5, 6, 7, 9]
    else:
        wave_ids = [int(w) for w in args.waves]

    all_pids: list[int] = []
    for w in wave_ids:
        if w not in WAVES:
            raise SystemExit(f"Unknown wave {w}")
        all_pids.extend(launch_wave(w, stagger_sec=args.stagger))

    print(f"Detached {len(all_pids)} runners. Monitor: {LOGROOT}/")
    print("PIDs:", " ".join(map(str, all_pids)))


if __name__ == "__main__":
    main()
