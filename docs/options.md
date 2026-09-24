Key point
With your current Fargate setup, there is no “cluster” per job: each Batch job is a single Fargate task with fixed vCPU/memory. Changing N in our env only changes what your code thinks, not how many machines AWS actually runs.
To get real 25 vs 50 node experiments, you need one of these patterns:
Option 1 – EC2 Batch compute environment (real nodes per job)
Create an EC2 compute environment for AWS Batch (e.g. chemo-ec2-env) with:
Instance type family you want (e.g. m5.xlarge).
Max vCPUs large enough (e.g. 200).
Create a job definition with container image and no fixed vCPU/memory, letting us override.
In run_batch_experiment, switch to this EC2 queue and use:
   container_overrides={       "vcpus": vcpus_per_node * n,       "memory": int(gb_per_node * 1024 * n),       "environment": [..., {"name": "N_NODES", "value": str(n)}],   }
Now N=25 vs N=50 literally requests 25× or 50× the per‑node vCPU/mem from Batch.
Each job is a single big EC2 instance (or set of instances) with that capacity; your code can then spawn N worker processes to actually use those cores.
This gives you real AWS capacity scaling per job, although it’s “bigger machines” not many tiny ones.
Option 2 – Multi‑job “cluster” (Batch array jobs)
If the descriptor computation is embarrassingly parallel, you can simulate a cluster:
For each (D, N):
Split the dataset into N shards.
Submit N separate Batch jobs (or an array job) each working on one shard.
When all N are done, merge results and log a single timing row for that (D, N).
Here “nodes” are truly N independent Batch jobs running in parallel on your compute environment. You’d measure:
Time from first job submit → all N jobs finished.
Cost = sum of all N jobs’ runtime × vCPU pricing.
This is closer to a real cluster than the Fargate‑single‑task pattern, and works with both EC2 and Fargate compute envs.
Option 3 – Stay on Fargate but map N to vCPU
If you want to keep Fargate, the only real knob is task size (vCPU/mem):
Create a Fargate job definition that allows vCPU/memory overrides.
For (D, N) set:
  container_overrides={      "resourceRequirements": [          {"type": "VCPU", "value": str(vcpus_per_node * N)},          {"type": "MEMORY", "value": str(gb_per_node * 1024 * N)},      ],      "environment": [...],  }
This gives you “N× bigger Fargate task” per job (more cores, more RAM), not N separate nodes, but you do pay for and can use N× capacity and compare 25 vs 50.
If you tell me which direction you prefer (EC2 env, array jobs, or “bigger Fargate task per N”), I can then:
Adjust run_experiment.py accordingly, and
Add the cost USD calculation for each job using the official pricing for your region and mode (on‑demand vs spot).


Option 1 – EC2 Batch env with vCPU overrides
N scales total vCPUs and memory requested: 25 vs 50 cores etc.
If your code parallelizes well, N=50 should be faster but more expensive; cost roughly scales with vCPU_hours, so 50 cores for half the time ≈ same vCPU cost, plus some differences from overhead.
Option 2 – Array jobs (N separate tasks)
N is N independent jobs; they can run in parallel up to cluster capacity.
Wall‑clock time ≈ time of the slowest shard, cost ≈ sum of all N tasks’ vCPU×time.
This is the most “cluster‑like” behavior.
Option 3 – Bigger Fargate task per N
N controls task size (more vCPUs/memory in a single task).
Similar to EC2 override case: if work parallelizes, bigger task → faster but higher per‑second price; total vCPU‑seconds can be similar.
So: right now, for your Fargate env, N does not change AWS capacity, so costs & times are not reflecting real 25 vs 50 node experiments. The three options would give different scaling behaviors and slightly different overheads, but similar total cost if you normalize by total vCPU‑seconds.


Which option best matches your paper?
Given the AGENTS rules and your performance model:
T
(
N
,
D
)
=
a
+
b
N
+
c
D
+
d
N
2
+
e
N
D
,
N
∗
(
D
)
=
−
b
+
e
D
2
d
T(N,D)=a+bN+cD+dN 
2
 +eND,N 
∗
 (D)=− 
2d
b+eD
​
 
where N is “number of compute nodes”, the best match is:
✅ Option 2 — Multi‑job “cluster” (array jobs / N separate tasks)
Why this fits the paper best:
N = number of nodes: with array jobs, you literally have N independent Batch tasks (each on its own EC2 instance or slot) working on shards of the same dataset. That’s exactly how N is treated in the math: more nodes → more parallel workers.
Distributed descriptor computation: descriptor generation is embarrassingly parallel over molecules; splitting a SMILES dataset into N chunks and running N jobs is a natural “distributed” setup, aligned with the paper’s framing.
Cost and time behave like the model assumes:
Wall time ≈ time of the slowest node (plus overhead), which matches the 
T
(
N
,
D
)
T(N,D) shape you’re modeling.
Cost ≈ sum of all N nodes’ vCPU×time, which is what you want when comparing N vs N′.
Works well with EC2 Spot, as recommended in AGENTS.md (c5.x family, Spot by default), and matches the “Optimal Resource Allocation” story (choose N given D to minimize cost/time).
The other options distort N:
Single big EC2 or Fargate task (Option 1/3): N becomes “total vCPUs on one machine”, not “number of nodes”; still usable, but less faithful to “distributed nodes” as in the paper.
Current Fargate single‑task setup: N is only an internal parameter; AWS actually runs 1 node, so it doesn’t reflect the model at all.
So, for experiments you’ll compare to the paper and for learning the N\*(D) curve, you should aim for array jobs / N parallel tasks on an EC2 Spot compute environment.



1. AWS setup (one‑time)
1.1 Create EC2 Spot compute environment
In AWS Console → Batch → Compute environments → Create:
Name: chemo-ec2-spot-env
Orchestration type: Amazon EC2
Provisioning model: SPOT
Instance types: c5.2xlarge, c5.4xlarge, c5.9xlarge
Min vCPUs: 0
Max vCPUs: e.g. 256
Desired vCPUs: 0
Subnets / security groups: same VPC as your current Fargate env.
Tags (recommended):
Project=cheminformatics-descriptors
Environment=research
Create it and wait until status is VALID.
1.2 Create EC2 job definition for worker
AWS Batch → Job definitions → Create:
Name: chemo-ec2-worker
Type: EC2
Image: same image you use now for Fargate worker.
vCPUs / Memory: set something minimal, but allow overrides:
vCPUs: 1
Memory: 2048 MB
Environment variables (base):
MODE=worker
Anything you already pass now (e.g. S3 bucket, region).
Save. We’ll override vCPU/memory per task if needed, but for array jobs you can also keep a fixed size per node.
1.3 Create EC2 job queue
AWS Batch → Job queues → Create:
Name: chemo-ec2-queue
Priority: 1
Scheduling policy: you can reuse chemo-fair-share-policy or keep FIFO.
Connected compute environments: chemo-ec2-spot-env.
Update .env later to include:
AWS_BATCH_JOB_QUEUE=chemo-ec2-queueAWS_BATCH_JOB_DEFINITION=chemo-ec2-worker
2. Code changes (what we’ll implement next)
We’ll adjust run_experiment.py to implement Option 2 – multi‑job cluster.
Conceptually:
Sharding the dataset
For each (D, N):
Read datasets/samples/smiles_{D}_{complexity}.csv.
Split its rows into N roughly equal chunks.
Write shard files to S3, e.g.:
     s3://<bucket>/<prefix>/D{D}_N{N}/shard_{i}.csv  for i = 0..N-1
Submitting N jobs (array job)
Submit one Batch array job with arrayProperties: { size: N }, or N separate jobs.
Each job gets:
DATASET_S3_BUCKET
DATASET_S3_PREFIX=D{D}_N{N}
SHARD_INDEX (0..N-1 from AWS_BATCH_JOB_ARRAY_INDEX)
Worker container reads its own shard, computes descriptors, and writes results back to S3 (e.g. results/shard_{i}.json).
Polling until cluster finishes
For array jobs:
Poll describe_jobs on the parent/children until all N are SUCCEEDED / FAILED.
Record:
cluster_start = first submit time.
cluster_end = when the last child finished.
Our ExperimentTimer’s computation_sec for that (D,N) is cluster_end - cluster_start.
Merging and logging
After cluster finishes, optionally read shard outputs from S3 to compute any aggregate metrics.
Build result_row for this (D,N):
dataset_size = D
n_nodes = N
execution_time = computation_sec
status = SUCCEEDED/FAILED (if any shard fails, mark failed).
Immediately:
Append to results list.
Send to Google Sheets (append_timing_result).
Later, save full results list into experiments/results/batch_compute_only_*.json.
Cost calculation
For each (D,N) cluster:
For each child job, fetch from describe_jobs:
vcpus, memory (from job def/override).
startedAt, stoppedAt → runtime_sec.
Using EC2 Spot pricing for eu-central-1 and chosen c5.* instance types, compute:
cost_node
=
(
vcpus
×
p
vCPU
+
memory_GB
×
p
GB
)
×
runtime_sec
3600
cost_node=(vcpus×p 
vCPU
​
 +memory_GB×p 
GB
​
 )× 
3600
runtime_sec
​
 
cost_usd = sum(cost_node over all N children).
Put cost_usd into result_row so your “Cost (USD)” column in Results is filled.
We’ll keep the existing Fargate path working for now, but add a new mode or branch for “EC2 multi‑node cluster” runs.
