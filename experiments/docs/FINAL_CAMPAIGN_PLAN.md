# Final Campaign Plan — Closing Paper §8 Limitations

**Status:** ✅ LIMITATIONS CLOSED (2026-08-15 08:48 UTC) — Waves **1 → 3 → 4** all OK, `failed=[]`  
**Follow-up (2026-08-17):** interleaved D=20k/D=40k 2-rep rerun to isolate time-of-day Spot vs D-scaling — `python scripts/run_interleaved_d20_d40.py`  
**Scope cut:** Waves **2, 5, 6, 7, 8, 9 cancelled** (Future Work / not stated Limitations).  
**Wave 1:** CLOSED — N=128 @ D=5k low/med + D=10k med  
**Wave 3:** CLOSED — D=50k low + medium full pow2 sweeps  
**Wave 4:** CLOSED — +2 reps @ D=20k/40k low + medium  
**Wall time (W3+W4 run):** ~14.8 h (2026-08-14 17:58 → 2026-08-15 08:48 UTC)  
**Logs:** `tmp/final_campaign/residual/` · state: `orchestrator_state.json`  
**Root cause fix (N=128):** ceil-split skipped empty trailing shards → Batch children 404.  
`run_experiment.py` now uploads all N shards (empty CSV allowed). Verified: 128/128 on S3.

## Prerequisite (done 2026-08-12)

Root cause of the **3 missing N=128 cells** was `maxvCpus=256` on both CEs (128 × 4 vCPU = 512). Bumped to **1024**:

```bash
python scripts/bump_ce_max_vcpus.py --max-vcpus 1024
```

Verify: both `chemo-ec2-worker-ondemand` and `chemo-ec2-worker` show `maxvCpus=1024`.

## Active waves → paper Limitations (§8)

| Wave | Experiment IDs | Closes |
|------|----------------|--------|
| **1** ✅ | `residual_w1_*_n128_od_*` | Limitation 1 — N=128 @ D=5k med, D=10k med |
| **3** | `residual_w3_d50k_pow2_spot_*` | Limitation 2 — D=50k full replicated sweep |
| **4** | `residual_w4_d{20,40}k_*_rep2` | Limitation 4 — +2 reps @ D=20k/40k (tighten R²) |

Limitation 3 (continuous complexity) is **Future Work** — not in this campaign.

## Cancelled (Future Work / optional — do not queue)

| Wave | Why cancelled |
|------|----------------|
| **2** | Nice-to-have; table already shows D=10k low untested (sunk: 1 job already ran) |
| **5** | High tier — Future Work |
| **6–7** | D=100k / N=256 — Future Work (largest cost) |
| **8** | mid-N 12/20/24 — Future Work |
| **9** | N=150/185 — not in paper Limitations |

## Datasets to generate (waves 5–7)

```bash
./scripts/generate_final_campaign_datasets.sh
```

Creates: `smiles_{5000,20000,40000}_high.csv`, `smiles_100000_{low,medium}.csv`.

## Recommended run order

1. **Wave 1** — unblocks 49/49 grid (On-Demand, 3 reps × 3 cells)  
2. **Wave 2 + 8** — moderate cost, high paper value (D=10k low + mid-N)  
3. **Wave 4** — +2 reps at D=20k/40k (runs while 1 completes)  
4. **Wave 3** — D=50k full replication  
5. **Generate datasets** → **Wave 5** (high tier)  
6. **Generate 100k** → **Wave 6** then **Wave 7**  
7. **Wave 9** — boundary re-verify (`BATCH_RETRY_ATTEMPTS=4`)

```bash
# Examples
./scripts/run_final_campaign.sh 1
./scripts/run_final_campaign.sh 2 4 8
./scripts/run_final_campaign.sh all   # sequential waves; long-running
```

Logs: `tmp/final_campaign/wave_<n>/master.log`

## Analysis merge rule (unchanged)

Pool all `final_w*` + prior `rep3_*` / `probe_*` by `(D, N, complexity)`; median timings; refit `T(N,D)` and complexity-extended models after each wave.

## Cost / capacity notes

- N=256 @ D=100k uses full 1024 vCPU ceiling — run one complexity at a time if placement fails.
- Wave 9 documents **failure boundary**, not grid completion — FAILED runs are valid outcomes.
- Spot preferred except Wave 1 (OD gap fix) and Wave 7 (OD parity at D=100k).

## After campaign

1. Regenerate Panels A–I from pooled Sheets data.  
2. Refit Table 3 with 5+ reps at D=20k/40k.  
3. Add high-tier / D=100k rows to Limitations → Results (not Limitations).  
4. Update `CLAUDE_HANDOFF_FULL_CAMPAIGN.md` with new experiment IDs.
