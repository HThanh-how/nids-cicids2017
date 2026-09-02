# Serving benchmark

The artefact behind the deployment section of the paper. The offline study
(`../experiments/run_v3.py`) says how accurate the model is; this directory
says what it costs to actually serve it.

## Why it exists

Both ICTA reviewers rejected the earlier deployment claims for the same
reason: the paper described an architecture and then quoted a throughput
figure extrapolated from per-sample model cost. That extrapolation ignores
feature handling, request parsing, serialisation, transport and concurrency.
What follows measures the deployed service end to end instead.

## Pipeline

```bash
# 1. freeze the model the service will run (same pipeline as the offline study)
python train_serving_model.py

# 2. start the service
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1

# 3. measure it
python loadtest/bench.py --url http://127.0.0.1:8000 \
    --concurrency 1,8,32,128 --duration 20
```

Results land in `../experiments/results_v3/S9_serving.json`.

## What is measured where

| Question the reviewer asked | Where it is answered | Needs a cluster |
|---|---|---|
| End-to-end latency distribution, not a mean | `bench.py`, p50/p90/p95/p99/p99.9 | no |
| Throughput vs concurrency, and the saturation point | `bench.py` concurrency sweep | no |
| Per-record vs amortised serving | `bench.py` batch-size sweep | no |
| Model cost vs queueing | `X-Server-Time-Ms` vs wall latency | no |
| Model load / cold start | `/readyz` gap, `load_seconds` in `/meta` | partly |
| Autoscaling behaviour | `k8s/hpa.yaml` + `k6.js` ramp | **yes** |
| Recovery after pod loss | delete a pod under load, count failures | **yes** |
| Resource envelope the numbers belong to | `k8s/deployment.yaml` requests/limits | **yes** |

The rows marked *yes* require Kubernetes and are the only part of the
deployment evaluation that cannot be produced on a workstation. Anything not
measured is reported as not measured; nothing here is extrapolated.

## Files

- `train_serving_model.py` — fits and freezes model + scaler statistics, and
  exports 2 000 held-out flows the load generator replays, so the benchmark
  sends real traffic rather than synthetic vectors.
- `app.py` — FastAPI service; `/healthz`, `/readyz`, `/meta`, `/predict`,
  `/predict/batch`, and an `X-Server-Time-Ms` header on every response.
- `Dockerfile` — pinned image, non-root, one worker per pod so that pod-level
  scaling is not confounded by in-process parallelism.
- `k8s/` — Deployment (with probes and explicit requests/limits), NodePort
  Service, HPA with explicit scale-up/down windows.
- `loadtest/bench.py` — closed-loop async load generator (primary instrument).
- `loadtest/k6.js` — the same profile for k6, for the cluster run.
