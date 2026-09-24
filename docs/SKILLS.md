# 🛠️ SKILLS.md — Reusable Patterns & Utilities
# Reference these patterns when implementing features

---

## Skill 1: AWS Batch Job Submission

```python
# src/aws/batch_manager.py pattern
import boto3
from dataclasses import dataclass
from typing import Optional
from loguru import logger

@dataclass
class BatchJobConfig:
    job_name: str
    job_queue: str           # e.g. "cheminformatics-queue"
    job_definition: str      # e.g. "descriptor-computation:latest"
    dataset_s3_prefix: str   # e.g. "chemoinformatics/D10000_N25"
    n_nodes: int             # array size to test
    dataset_size: int        # number of compounds
    vcpus: int = 4
    memory_mb: int = 8192

def submit_batch_job(config: BatchJobConfig) -> str:
    """Submit array job, return parent job ID."""
    client = boto3.client("batch", region_name=os.getenv("AWS_REGION", "us-east-1"))
    response = client.submit_job(
        jobName=config.job_name,
        jobQueue=config.job_queue,
        jobDefinition=config.job_definition,
        arrayProperties={"size": config.n_nodes},
        containerOverrides={
            "vcpus": config.vcpus,
            "memory": config.memory_mb,
            "environment": [
                {"name": "DATASET_S3_PREFIX", "value": config.dataset_s3_prefix},
                {"name": "N_NODES", "value": str(config.n_nodes)},
                {"name": "DATASET_SIZE", "value": str(config.dataset_size)},
            ]
        }
    )
    job_id = response["jobId"]
    logger.info(f"Submitted job {config.job_name} → {job_id}")
    return job_id
```

---

## Skill 2: S3 Dataset Upload

```python
# src/aws/s3_manager.py pattern
import boto3
from pathlib import Path
from loguru import logger

def upload_dataset(local_path: Path, bucket: str, s3_key: str) -> str:
    """Upload dataset CSV to S3, return full S3 URI."""
    s3 = boto3.client("s3")
    s3.upload_file(
        str(local_path),
        bucket,
        s3_key,
        ExtraArgs={"ServerSideEncryption": "AES256"}
    )
    uri = f"s3://{bucket}/{s3_key}"
    logger.success(f"Uploaded {local_path.name} → {uri}")
    return uri

def check_or_upload(local_path: Path, bucket: str, s3_key: str) -> str:
    """Upload only if not already in S3 (idempotent)."""
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=s3_key)
        logger.info(f"Dataset already in S3: s3://{bucket}/{s3_key}")
    except s3.exceptions.ClientError:
        upload_dataset(local_path, bucket, s3_key)
    return f"s3://{bucket}/{s3_key}"
```

---

## Skill 3: Performance Model (from paper)

```python
# src/core/model.py pattern
import numpy as np
from dataclasses import dataclass
from sklearn.linear_model import LinearRegression

@dataclass
class ModelCoefficients:
    a: float  # intercept / baseline
    b: float  # linear N (node benefit)
    c: float  # linear D (data cost)
    d: float  # quadratic N (overhead)
    e: float  # interaction ND

    def predict(self, n_nodes: int, dataset_size: int) -> float:
        """T(N,D) = a + bN + cD + dN² + eND"""
        N, D = n_nodes, dataset_size
        return self.a + self.b*N + self.c*D + self.d*N**2 + self.e*N*D

    def optimal_nodes(self, dataset_size: int, n_min: int = 1, n_max: int = 200) -> int:
        """N*(D) = -(b + eD) / (2d), clamped to [n_min, n_max]"""
        D = dataset_size
        n_star = -(self.b + self.e * D) / (2 * self.d)
        return int(np.clip(round(n_star), n_min, n_max))

def fit_model(experiment_results: list[dict]) -> ModelCoefficients:
    """
    Fit T(N,D) = a + bN + cD + dN² + eND from experiment data.
    experiment_results: list of {"n_nodes": int, "dataset_size": int, "execution_time": float}
    """
    rows = []
    y = []
    for r in experiment_results:
        N, D = r["n_nodes"], r["dataset_size"]
        rows.append([N, D, N**2, N*D])
        y.append(r["execution_time"])
    
    X = np.array(rows)
    reg = LinearRegression().fit(X, y)
    b, c, d, e = reg.coef_
    a = reg.intercept_
    return ModelCoefficients(a=a, b=b, c=c, d=d, e=e)
```

---

## Skill 4: Google Sheets Sync

```python
# src/monitoring/sheets.py pattern
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from loguru import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet(sheet_id: str, worksheet_name: str):
    """Authenticate and return worksheet."""
    creds = Credentials.from_service_account_file(
        "credentials/google_service_account.json", scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    return sh.worksheet(worksheet_name)

def append_result(sheet_id: str, result: dict) -> None:
    """Append one experiment result row to Google Sheets."""
    ws = get_sheet(sheet_id, "Results")
    row = [
        datetime.utcnow().isoformat(),
        result.get("experiment_id"),
        result.get("dataset_size"),
        result.get("n_nodes"),
        result.get("execution_time"),
        result.get("cost_usd"),
        result.get("smiles_complexity"),
        result.get("job_id"),
        result.get("status"),
    ]
    ws.append_row(row)
    logger.info(f"Sheet updated: D={result['dataset_size']}, N={result['n_nodes']}")
```

---

## Skill 5: SMILES Dataset Generation

```python
# datasets/generators/smiles_generator.py pattern
import random
import pandas as pd
from pathlib import Path

# Realistic SMILES building blocks
ATOMS = ["C", "N", "O", "S", "F", "Cl", "Br"]
BONDS = ["", "=", "#"]
BRANCHES = ["(C)", "(N)", "(O)", "(CC)", "(CCC)", "(c1ccccc1)"]
RINGS = ["c1ccccc1", "C1CCCC1", "c1ccncc1", "C1CCCCC1"]

def generate_smiles(target_length: int = 57, complexity: str = "medium") -> str:
    """Generate a plausible SMILES string of approximate target length."""
    # ... implementation using building blocks
    pass

def generate_dataset(
    n_compounds: int,
    avg_length: int = 57,
    complexity: str = "medium",  # low|medium|high
    output_path: Path = None,
    seed: int = 42
) -> pd.DataFrame:
    """Generate dataset of SMILES strings. Saves CSV if output_path given."""
    random.seed(seed)
    smiles_list = [generate_smiles(avg_length, complexity) for _ in range(n_compounds)]
    df = pd.DataFrame({"smiles": smiles_list, "id": range(n_compounds)})
    if output_path:
        df.to_csv(output_path, index=False)
    return df
```

---

## Skill 6: Experiment Estimator

```python
# experiments/estimator/experiment_estimator.py pattern
from src.core.model import ModelCoefficients

# Default coefficients from paper
DEFAULT_COEFFS = ModelCoefficients(a=500.0, b=-8.0, c=0.008, d=0.05, e=0.00002)

# AWS Batch pricing (us-east-1, approximate)
SPOT_PRICE_PER_VCPU_HOUR = 0.012   # c5.2xlarge spot ~$0.048/hr / 4 vCPUs
SPOT_PRICE_PER_GB_HOUR = 0.0015

def estimate_experiment(config: dict, coeffs: ModelCoefficients = DEFAULT_COEFFS) -> dict:
    """
    Given experiment config, return estimated:
    - total_time_seconds
    - total_cost_usd
    - recommended_n_nodes
    - time_per_config
    """
    dataset_sizes = config["dataset_sizes"]
    node_configs = config["node_configs"]
    vcpus_per_node = config.get("vcpus_per_node", 4)
    gb_per_node = config.get("gb_per_node", 8)
    
    total_time = 0
    total_cost = 0
    details = []
    
    for D in dataset_sizes:
        for N in node_configs:
            t = coeffs.predict(N, D)
            vcpu_hours = (t / 3600) * N * vcpus_per_node
            gb_hours = (t / 3600) * N * gb_per_node
            cost = vcpu_hours * SPOT_PRICE_PER_VCPU_HOUR + gb_hours * SPOT_PRICE_PER_GB_HOUR
            total_time += t
            total_cost += cost
            details.append({"D": D, "N": N, "t_sec": t, "cost": cost})
    
    return {
        "total_time_seconds": total_time,
        "total_cost_usd": total_cost,
        "details": details,
        "recommended_nodes": {D: coeffs.optimal_nodes(D) for D in dataset_sizes}
    }
```

---

## Skill 7: Rich Dashboard

```python
# src/monitoring/dashboard.py pattern
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

def render_dashboard(jobs: list[dict], model_coeffs, elapsed: float):
    """Render live TUI dashboard with job status + model predictions."""
    table = Table(title="Active Batch Jobs", show_header=True)
    table.add_column("Job ID", style="cyan")
    table.add_column("Dataset Size", style="magenta")
    table.add_column("Nodes", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Est. Time", style="blue")
    
    for job in jobs:
        est = model_coeffs.predict(job["n_nodes"], job["dataset_size"])
        table.add_row(
            job["job_id"][:8],
            str(job["dataset_size"]),
            str(job["n_nodes"]),
            job["status"],
            f"{est:.0f}s"
        )
    return table
```

---

## Common Patterns

### Retry with backoff
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def aws_call_with_retry():
    ...
```

### YAML experiment config loading
```python
import yaml
with open("experiments/configs/experiment_01.yaml") as f:
    config = yaml.safe_load(f)
```

### Timestamped result file
```python
from datetime import datetime
ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
result_path = Path(f"experiments/results/{ts}_{config['name']}.json")
```
