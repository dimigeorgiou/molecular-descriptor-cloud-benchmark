```bash
# Use Case 1 — Medium-complexity, default descriptors, full local pipeline (T(N, D, complexity))
python datasets/generators/smiles_generator.py \
  --sizes 5000 10000 \
  --complexity medium \
  --output-dir datasets/samples/

python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/experiment_00_quick.yaml \
  --dataset-dir datasets/samples/ \
  --verbose

python experiments/run_experiment.py \
  --config experiments/configs/experiment_00_quick.yaml \
  --local \
  --mode full_pipeline

# Use Case 2 — High-complexity SMILES + heavy descriptor method (slower T(N, D, complexity, method))
python datasets/generators/smiles_generator.py \
  --sizes 10000 \
  --complexity high \
  --output-dir datasets/samples/

python experiments/estimator/experiment_estimator.py \
  --config experiments/configs/experiment_00_quick.yaml \
  --dataset-dir datasets/samples/ \
  --verbose

python experiments/run_experiment.py \
  --config experiments/configs/experiment_00_quick.yaml \
  --local \
  --mode compute_only

# Use Case 3 — Upload-only benchmark for medium-complexity SMILES (estimating upload part of T)
python datasets/generators/smiles_generator.py \
  --sizes 5000 10000 20000 50000 \
  --complexity medium \
  --output-dir datasets/samples/

python experiments/run_experiment.py \
  --config experiments/configs/experiment_upload_benchmark.yaml \
  --local
```


