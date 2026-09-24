# Distributed Cheminformatics Descriptor Computation
### Optimal Resource Allocation via Analytical Performance Modeling

> **Research paper:** "Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics"  
> Didachos C., Georgiou D., Fousteris M., Kanavos A. — University of Patras / Ionian University

This project implements the paper's methodology end-to-end: generating SMILES datasets, running distributed descriptor computation on AWS Batch, fitting the T(N,D) performance model, and predicting optimal cluster sizes analytically — without trial-and-error.

---

## 📐 The Core Idea

The execution time model from the paper:

```
T(N, D) = a + bN + cD + dN² + eND
```

Where **N** = cluster nodes, **D** = dataset size (compounds). Setting dT/dN = 0:

```
N*(D) = -(b + eD) / (2d)   ← Optimal nodes for dataset size D
```

Since `d > 0`, this is a **global minimum** (convex function). You compute the ideal cluster size analytically — no repeated experiments needed.

---

## 🏗️ Project Structure

```
cheminformatics-distributed/
├── PLAN.md                         ← Cursor Pro: execute this
├── SKILLS.md                       ← Reusable code patterns
├── .cursor/AGENTS.md               ← Cursor agent configuration
│
├── src/
│   ├── core/
│   │   └── model.py                ← T(N,D) model, optimizer, fitter
│   ├── aws/
│   │   ├── batch_manager.py        ← AWS Batch job submission
│   │   └── s3_manager.py           ← S3 dataset management
│   ├── monitoring/
│   │   ├── sheets.py               ← Google Sheets sync
│   │   └── dashboard.py            ← Rich TUI live dashboard
│   └── worker/
│       └── compute_descriptors.py  ← Descriptor computation (runs in Batch)
│
├── experiments/
│   ├── run_experiment.py           ← Main runner (after estimator!)
│   ├── estimator/
│   │   └── experiment_estimator.py ← ⚠️ ALWAYS run before experiments
│   ├── configs/
│   │   ├── experiment_00_quick.yaml          ← Sanity check (2x2, ~$0.10)
│   │   ├── experiment_01_replication.yaml    ← Full paper replication
│   │   ├── experiment_02_complexity.yaml     ← SMILES complexity study
│   │   └── experiment_03_large_scale.yaml    ← 100k-500k compounds
│   └── results/                    ← All outputs (gitignored)
│
├── datasets/
│   ├── generators/
│   │   └── smiles_generator.py     ← Synthetic SMILES generation
│   └── samples/                    ← Generated CSVs (gitignored)
│
├── docker/
│   ├── Dockerfile                  ← Worker image for AWS Batch
│   └── entrypoint.sh               ← Container entrypoint
│
├── scripts/
│   ├── validate_setup.py           ← Pre-flight checks
│   ├── aws_setup.py                ← One-time AWS infrastructure
│   └── upload_datasets.py          ← Upload datasets to S3
│
├── credentials/                    ← Google service account (gitignored)
├── requirements.txt
└── .env.example                    ← Copy to .env and fill in
```

---

## 🚀 Quick Start

```bash
# 1. Clone and install
git clone <your-repo>
cd cheminformatics-distributed
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your AWS + Google credentials

# 3. Validate setup
python scripts/validate_setup.py

# 4. Generate datasets
python datasets/generators/smiles_generator.py --sizes 5000 10000 --complexity medium

# 5. ESTIMATE before running (always!)
python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/experiment_00_quick.yaml --verbose

# 6. Run sanity check experiment
python experiments/run_experiment.py \
  --config experiments/configs/experiment_00_quick.yaml

# 7. Monitor live
python src/monitoring/dashboard.py --watch
```

---

## ☁️ AWS Setup (one-time)

### Prerequisites
- AWS account with sufficient service limits for Batch
- AWS CLI installed and configured (`aws configure`)

### Step 1 — Create S3 Bucket

```bash
# Replace YOUR_BUCKET_NAME with a globally unique name
aws s3 mb s3://YOUR_BUCKET_NAME --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket YOUR_BUCKET_NAME \
  --versioning-configuration Status=Enabled
```

Add `S3_BUCKET=YOUR_BUCKET_NAME` to your `.env`.

### Step 2 — Create IAM Roles

You need 3 IAM roles. Create them in AWS Console → IAM → Roles.

#### 2a. AWSBatchServiceRole
- **Type:** AWS Service → Batch
- **Policy:** `AWSBatchServiceRole` (managed policy)
- **Name:** `AWSBatchServiceRole`

#### 2b. BatchInstanceRole (EC2 instance profile)
- **Type:** AWS Service → EC2
- **Policies:**
  - `AmazonEC2ContainerServiceforEC2Role` (managed)
  - Custom inline policy for S3 access:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
        "Resource": [
          "arn:aws:s3:::YOUR_BUCKET_NAME",
          "arn:aws:s3:::YOUR_BUCKET_NAME/*"
        ]
      }]
    }
    ```
- **Name:** `BatchInstanceRole`
- After creating, **create an Instance Profile** with the same name:
  ```bash
  aws iam create-instance-profile --instance-profile-name BatchInstanceRole
  aws iam add-role-to-instance-profile \
    --instance-profile-name BatchInstanceRole --role-name BatchInstanceRole
  ```

#### 2c. BatchJobRole (job-level permissions)
- **Type:** AWS Service → EC2 (or use ECS task role)
- **Policies:**
  - Same S3 inline policy as above
  - `CloudWatchLogsFullAccess` (or scoped to `/aws/batch/cheminformatics`)
- **Name:** `BatchJobRole`

Set the ARNs in your `.env`:
```bash
AWS_INSTANCE_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:instance-profile/BatchInstanceRole
AWS_BATCH_SERVICE_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/AWSBatchServiceRole
AWS_JOB_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/BatchJobRole
```

### Step 3 — Get VPC Subnet & Security Group

```bash
# List your default VPC subnets
aws ec2 describe-subnets \
  --filters "Name=defaultForAz,Values=true" \
  --query "Subnets[*].[SubnetId,AvailabilityZone]" \
  --output table

# Get default security group
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=default" \
  --query "SecurityGroups[*].[GroupId,VpcId]" \
  --output table
```

Add to `.env`:
```bash
AWS_SUBNET_ID=subnet-xxxxxxxxxxxxxxxxx   # comma-separate multiple
AWS_SECURITY_GROUP_ID=sg-xxxxxxxxxxxxxxxxx
```

### Step 4 — Create AWS Batch Infrastructure

```bash
python scripts/aws_setup.py --create-all
```

This creates:
- ✅ Compute environment (`cheminformatics-ce`) — Spot c5 instances, scales to 0 when idle
- ✅ ECR repository for Docker images
- ✅ Job queue (`cheminformatics-queue`)
- ✅ Job definition (`descriptor-worker:latest`)

Verify it worked:
```bash
python scripts/aws_setup.py --status
```

### Step 5 — Build & Push Docker Image

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build
cd docker/
docker build -t descriptor-worker .

# Tag and push
docker tag descriptor-worker:latest \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cheminformatics-descriptor-worker:latest
docker push \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cheminformatics-descriptor-worker:latest
```

---

## 📊 Google Sheets Monitoring Setup

### Step 1 — Create Google Cloud Project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create new project: `cheminformatics-monitoring`
3. Enable **Google Sheets API** and **Google Drive API**

### Step 2 — Create Service Account
1. IAM & Admin → Service Accounts → Create
2. Name: `sheets-monitor`
3. Download JSON key → save as `credentials/google_service_account.json`

### Step 3 — Create & Share Google Sheet
1. Create a new Google Sheet at [sheets.google.com](https://sheets.google.com)
2. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/`**`YOUR_SHEET_ID`**`/edit`
3. Click **Share** → paste the service account email (from the JSON, `client_email` field)
4. Grant **Editor** access

### Step 4 — Configure
```bash
GOOGLE_SHEET_ID=YOUR_SHEET_ID_FROM_URL
GOOGLE_CREDENTIALS_PATH=credentials/google_service_account.json
```

### Step 5 — Test
```bash
python src/monitoring/sheets.py check
# → ✅ Sheet 'Experiment Results' accessible. 0 result rows found.
```

---

## 🧪 Running Experiments

### ⚠️ ALWAYS estimate first!

```bash
python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/experiment_01_replication.yaml \
  --verbose
```

This shows:
- Estimated wall time
- Estimated cost (Spot pricing)
- Optimal node counts per dataset size
- Per-config breakdown

### Experiment 00 — Quick Sanity Check (start here!)
```bash
python experiments/run_experiment.py \
  --config experiments/configs/experiment_00_quick.yaml
```
- 2×2 grid (2 datasets × 2 node configs)
- ~15 min, ~$0.10

### Experiment 01 — Paper Replication
```bash
python experiments/run_experiment.py \
  --config experiments/configs/experiment_01_replication.yaml
```
- 6 dataset sizes × 8 node configs × 3 replicas = 144 jobs
- Replicates Table 1 from the paper
- ~2-3 hours, ~$2-5

### Experiment 02 — SMILES Complexity Study (paper extension)
```bash
python experiments/run_experiment.py \
  --config experiments/configs/experiment_02_complexity.yaml
```
- Tests low/medium/high SMILES complexity
- Extends paper's conclusion: "investigate molecular complexity"

### Experiment 03 — Large Scale
```bash
# Estimate first — this one can be expensive
python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/experiment_03_large_scale.yaml

python experiments/run_experiment.py \
  --config experiments/configs/experiment_03_large_scale.yaml
```

### Dry run (no jobs submitted)
```bash
python experiments/run_experiment.py \
  --config experiments/configs/experiment_01_replication.yaml \
  --dry-run
```

---

## 📈 Model & Analysis

### Fit the performance model from collected data
```bash
python src/core/model.py fit
```

### Compute optimal nodes table
```bash
python src/core/model.py optimal-table
```
Output:
```
    Dataset Size    Optimal Nodes    Predicted Time (s)
           5,000               42                 201.3
          10,000               73                 183.1
          20,000              101                 263.6
          50,000              185                 307.0
```

### Predict for custom config
```bash
python src/core/model.py predict 145 10000
# T(N=145, D=10000) = 152.2s
```

---

## 🖥️ Live Monitoring Dashboard

```bash
# Launch live TUI dashboard (refreshes every 30s)
python src/monitoring/dashboard.py --watch

# Filter to specific experiment
python src/monitoring/dashboard.py --watch --experiment-id 20250315_123456_exp01

# Sync all results to Google Sheets
python src/monitoring/sheets.py sync-all --results-dir experiments/results/
```

---

## 💰 Cost Optimization Tips

1. **Always use Spot instances** (`use_spot: true` in configs) — ~80% cheaper
2. **Run estimator first** — avoid surprises
3. **Compute environment scales to 0** — no idle costs
4. **Start with experiment_00** — validate pipeline before full runs
5. **Use `SPOT_CAPACITY_OPTIMIZED`** strategy — AWS picks cheapest available Spot pool
6. **Preferred instance types:** `c5.2xlarge`, `c5.4xlarge` — compute-optimized, great for descriptor work

---

## 🔬 Adding New Experiments

1. Create `experiments/configs/experiment_XX_name.yaml`
2. Set `dataset_sizes`, `node_configs`, `smiles_complexity`
3. Run estimator: `python experiments/estimator/experiment_estimator.py --config ...`
4. Run: `python experiments/run_experiment.py --config ...`

To add a new SMILES complexity level, edit `datasets/generators/smiles_generator.py` and add entries to `COMPLEXITY_PARAMS`.

---

## 📦 Key Dependencies

| Package | Purpose |
|---------|---------|
| `boto3` | AWS Batch + S3 |
| `gspread` + `google-auth` | Google Sheets sync |
| `scikit-learn` | OLS regression for model fitting |
| `rich` | TUI dashboard |
| `loguru` | Structured logging |
| `rdkit` | Real molecular descriptors (optional) |

Install RDKit for real descriptor computation:
```bash
conda install -c conda-forge rdkit
```
Without RDKit, the worker uses synthetic descriptors (valid for benchmarking compute scaling).

---

## 📖 Paper Reference

```bibtex
@inproceedings{didachos2025optimal,
  title={Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics},
  author={Didachos, Christos and Georgiou, Dimitrios and Fousteris, Manolis and Kanavos, Andreas},
  institution={University of Patras / Ionian University},
  year={2025}
}
```

**Performance model (Section 4):**
T(N,D) = a + bN + cD + dN² + eND

**Optimal nodes formula (Section 5):**
N*(D) = -(b + eD) / (2d)

**Key results (Section 7):**
- 10k compounds: 198.9s (empirical) → 152.2s (analytical, 145 nodes) — **23% faster**
- 20k compounds: 263.6s → 183.1s — **31% faster**
- 50k compounds: 445.3s → 307.0s — **31% faster**
