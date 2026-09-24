"""
Validate local setup for the chemoinformatics descriptor project.

Runs in an "offline-friendly" mode by default: AWS and Google Sheets
credentials are optional and reported as warnings, not hard failures.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def check_python_packages() -> List[str]:
    """
    Check that required Python packages can be imported.
    Returns a list of missing package names.
    """
    required = [
        "numpy",
        "pandas",
        "sklearn",
        "loguru",
        "yaml",
        "rich",
    ]
    missing: List[str] = []
    for name in required:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        logger.error("Missing Python packages: {}", ", ".join(missing))
    else:
        logger.success("All core Python packages are importable.")
    return missing


def check_directories() -> List[str]:
    """
    Ensure key directories exist.
    Returns a list of missing directory paths (relative to project root).
    """
    required_dirs = [
        "src/core",
        "src/aws",
        "src/monitoring",
        "src/worker",
        "datasets/generators",
        "datasets/samples",
        "experiments/estimator",
        "experiments/configs",
        "experiments/results",
    ]
    missing: List[str] = []
    for rel in required_dirs:
        path = PROJECT_ROOT / rel
        if not path.exists():
            logger.error("Missing required directory: {}", rel)
            missing.append(rel)
    if not missing:
        logger.success("All key directories are present.")
    return missing


def check_env_offline_friendly() -> None:
    """
    Check AWS / Sheets configuration.

    AWS: env vars (after .env) OR default credential chain (~/.aws/credentials,
    SSO, etc.) — same resolution as boto3 used by run_experiment.
    """
    has_explicit_keys = bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    has_region = bool(os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))

    if has_explicit_keys and has_region:
        logger.success(
            "AWS env credentials present (AWS_ACCESS_KEY_ID / SECRET + region)."
        )
    elif has_explicit_keys and not has_region:
        logger.warning(
            "AWS keys set but AWS_REGION (or AWS_DEFAULT_REGION) missing — "
            "set region to match Batch/S3 (e.g. eu-central-1)."
        )
    else:
        # No keys in env: try default chain (CLI profile, etc.)
        try:
            import boto3

            sts = boto3.client("sts")
            ident = sts.get_caller_identity()
            arn = ident.get("Arn", "?")
            acct = ident.get("Account", "?")
            logger.success(
                "AWS reachable via default credential chain (e.g. ~/.aws/credentials): "
                "account={} … {}",
                acct,
                arn.split("/")[-1] if "/" in str(arn) else arn,
            )
            if not has_region:
                logger.warning(
                    "No AWS_REGION in env — boto3 may use ~/.aws/config default; "
                    "set AWS_REGION in .env if jobs fail with wrong region."
                )
        except Exception as exc:  # pragma: no cover - network / cred dependent
            logger.warning(
                "No AWS_ACCESS_KEY_ID/SECRET in env and default AWS chain failed: {}. "
                "Use `aws configure`, SSO, or .env — see README § Connecting to AWS.",
                exc,
            )

    if not os.getenv("GOOGLE_SHEETS_ID"):
        logger.warning(
            "GOOGLE_SHEETS_ID not set. Google Sheets sync will be disabled "
            "until you configure it (or add to .env)."
        )
    else:
        logger.success("Google Sheets ID is configured.")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    logger.info("Validating setup in offline-friendly mode…")
    missing_pkgs = check_python_packages()
    missing_dirs = check_directories()
    check_env_offline_friendly()

    if missing_pkgs or missing_dirs:
        logger.error("Setup validation completed with issues.")
    else:
        logger.success("Setup validation completed successfully.")


if __name__ == "__main__":
    main()

