# MASTER PROMPT — Cheminformatics Distributed Computation
# Paste this entire block into Cursor Pro Composer (Cmd+I / Ctrl+I)
# Make sure you have the project folder open in Cursor first.

---

You are implementing a research computing platform based on the paper:
"Optimal Resource Allocation for Distributed Descriptor Computation in Cheminformatics"

Your job is to build and wire together everything in this project so it runs end-to-end.
Read PLAN.md first, then SKILLS.md, then .cursor/AGENTS.md before writing any code.

## YOUR TASK LIST (execute in order, do not skip steps)

### STEP 1 — Read context files
Read these files before doing anything else:
- PLAN.md
- SKILLS.md
- .cursor/AGENTS.md
- src/core/model.py

### STEP 2 — Install dependencies
Run in terminal:
```
pip install -r requirements.txt
```
If any package fails, fix it and continue.

### STEP 3 — Generate sample datasets locally
Run:
```
python datasets/generators/smiles_generator.py \
  --sizes 5000 10000 20000 30000 40000 50000 \
  --complexity medium \
  --output-dir datasets/samples/
```
Verify CSV files appear in datasets/samples/.

### STEP 4 — Set up .env
Copy .env.example to .env.
The user will fill in real credentials — do NOT invent values.
Print a clear message showing what needs to be filled in.

### STEP 5 — Run the experiment estimator (no AWS needed)
Run:
```
python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/experiment_00_quick.yaml \
  --verbose
```
This should work WITHOUT AWS credentials (uses paper model estimates).
Fix any import errors or missing modules until it prints the cost/time table.

### STEP 6 — Validate model math
Run:
```
python src/core/model.py optimal-table
```
Expected output: a table showing optimal nodes for dataset sizes 5k–50k.
The 10k row should show ~73 nodes and ~183s (matches paper Section 7).

### STEP 7 — Fix any broken imports
Run validate_setup.py in "offline mode" (skip AWS checks):
```
python scripts/validate_setup.py
```
Fix any Python dependency errors. AWS checks will fail without credentials — that is OK.

### STEP 8 — Wire up missing pieces
Check these files exist and are complete:
- src/core/model.py ✓
- src/aws/batch_manager.py ✓
- src/aws/s3_manager.py ✓
- src/monitoring/sheets.py ✓
- src/monitoring/dashboard.py ✓
- src/worker/compute_descriptors.py ✓
- experiments/estimator/experiment_estimator.py ✓
- experiments/run_experiment.py ✓
- datasets/generators/smiles_generator.py ✓

If any are missing or have syntax errors, fix them now.

### STEP 9 — Run a LOCAL experiment (no AWS, simulated)
Add a --local flag to experiments/run_experiment.py that:
- Skips AWS Batch submission
- Runs compute_descriptors.py directly on the local machine
- Uses a subset: dataset_sizes [5000] and node_configs [25, 50]
- Writes results to experiments/results/local_test_TIMESTAMP.json

Then run:
```
python experiments/run_experiment.py \
  --config experiments/configs/experiment_00_quick.yaml \
  --local
```

### STEP 10 — Fit the model from local results
After Step 9 produces results, run:
```
python src/core/model.py fit
```
This should fit T(N,D) from local data and save experiments/results/fitted_model.json.

### STEP 11 — Launch dashboard (local mode)
Run:
```
python src/monitoring/dashboard.py
```
(Without --watch so it renders once and exits cleanly.)
Fix any Rich rendering errors.

### STEP 12 — Final smoke test
Run this sequence end-to-end without errors:
```bash
python datasets/generators/smiles_generator.py --sizes 5000 --complexity medium --output-dir datasets/samples/
python experiments/estimator/experiment_estimator.py --config experiments/configs/experiment_00_quick.yaml
python experiments/run_experiment.py --config experiments/configs/experiment_00_quick.yaml --local
python src/core/model.py fit
python src/core/model.py optimal-table
python src/monitoring/dashboard.py
```
If any step fails, fix it before continuing.

## RULES FOR THIS SESSION
- Read SKILLS.md before writing any new function — use the patterns there
- Never hardcode AWS credentials
- Every fix must be tested by actually running the command
- If something is unclear, check AGENTS.md before asking
- Write to experiments/results/ for all outputs
- Use loguru for all logging (never print() in src/)
- After each step, confirm it worked before moving to the next

## WHAT SUCCESS LOOKS LIKE
At the end of this session:
1. `python experiments/estimator/experiment_estimator.py --config experiments/configs/experiment_00_quick.yaml` runs cleanly and shows a cost table
2. `python experiments/run_experiment.py --config experiments/configs/experiment_00_quick.yaml --local` runs and writes results JSON
3. `python src/core/model.py optimal-table` shows predicted optimal nodes matching the paper
4. The project is ready for the user to fill in .env and run against real AWS

Go.
