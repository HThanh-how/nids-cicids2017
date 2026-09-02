"""
Intrusion-detection inference service.

This is the artefact behind the deployment claims in the paper. Everything the
evaluation needs to measure is exposed deliberately:

  GET  /healthz        liveness  -- answers as soon as the process is up
  GET  /readyz         readiness -- 503 until the model is loaded, so a cold
                       start can be timed from outside the container
  GET  /meta           model identity, feature order, artefact metrics
  POST /predict        one flow   (the per-record path)
  POST /predict/batch  many flows (the amortised path)

Every response carries an X-Server-Time-Ms header holding the server-side
processing time, so the load generator can separate model cost from queueing
and transport.
"""

import json
import os
import time
from typing import Dict, List

import numpy as np
import joblib
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ART = os.environ.get("ARTIFACT_DIR",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "artifacts"))

app = FastAPI(title="IDS inference service", version="3.0")

STATE: Dict[str, object] = {"ready": False}


@app.on_event("startup")
def _load() -> None:
    t0 = time.perf_counter()
    with open(os.path.join(ART, "metadata.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    model = joblib.load(os.path.join(ART, "model.joblib"))
    mean = np.asarray(meta["selected_mean"], dtype=np.float64)
    scale = np.asarray(meta["selected_scale"], dtype=np.float64)
    scale[scale == 0] = 1.0

    STATE.update({
        "meta": meta,
        "model": model,
        "features": meta["selected_features"],
        "mean": mean,
        "scale": scale,
        "load_seconds": time.perf_counter() - t0,
        "ready": True,
    })
    # Warm the prediction path: the first call into XGBoost allocates buffers
    # and would otherwise show up as a spurious cold-start outlier.
    model.predict(np.zeros((1, len(mean)), dtype=np.float32))
    print(f"[startup] model loaded in {STATE['load_seconds']:.3f}s, "
          f"{len(mean)} features")


class Flow(BaseModel):
    features: List[float]


class FlowBatch(BaseModel):
    flows: List[List[float]]


def _score(rows: np.ndarray) -> np.ndarray:
    z = (rows - STATE["mean"]) / STATE["scale"]
    return STATE["model"].predict_proba(z.astype(np.float32))[:, 1]


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "alive"}


@app.get("/readyz")
def readyz() -> Response:
    if not STATE.get("ready"):
        return JSONResponse({"status": "loading"}, status_code=503)
    return JSONResponse({"status": "ready",
                         "load_seconds": STATE["load_seconds"]})


@app.get("/meta")
def meta() -> Dict[str, object]:
    m = STATE["meta"]
    return {
        "model": m["model"],
        "n_features": len(m["selected_features"]),
        "features": m["selected_features"],
        "offline_metrics_random_split": m["offline_metrics_random_split"],
        "load_seconds": STATE["load_seconds"],
    }


@app.post("/predict")
def predict(flow: Flow, response: Response) -> Dict[str, object]:
    t0 = time.perf_counter()
    p = float(_score(np.asarray([flow.features], dtype=np.float64))[0])
    response.headers["X-Server-Time-Ms"] = f"{1000 * (time.perf_counter() - t0):.4f}"
    return {"attack_probability": p, "prediction": int(p >= 0.5)}


@app.post("/predict/batch")
def predict_batch(batch: FlowBatch, response: Response) -> Dict[str, object]:
    t0 = time.perf_counter()
    probs = _score(np.asarray(batch.flows, dtype=np.float64))
    dt = time.perf_counter() - t0
    response.headers["X-Server-Time-Ms"] = f"{1000 * dt:.4f}"
    return {
        "n": int(len(probs)),
        "attack_probability": [float(v) for v in probs],
        "prediction": [int(v >= 0.5) for v in probs],
        "server_ms_per_flow": 1000 * dt / len(probs),
    }


@app.middleware("http")
async def _timing(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["X-Total-Time-Ms"] = f"{1000 * (time.perf_counter() - t0):.4f}"
    return resp
