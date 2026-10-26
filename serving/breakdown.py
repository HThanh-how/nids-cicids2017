"""
Where does a single-flow request spend its time?  (Reviewer 6, Q2)

Two measurements, each at the library default thread setting (as in S9) and
with the maths libraries pinned to one thread (as the image sets, S10):

  1. In process, no HTTP: the exact code path of app.py split into its
     stages -- JSON parse + pydantic validation of the request body, array
     construction + standardisation, the model call for one row, and response
     serialisation -- against the amortised per-row cost of one batch call.
  2. Over HTTP at one closed-loop client (no queueing): client-observed
     latency, the app's X-Total-Time-Ms (framework: routing, parsing,
     validation, handler, serialisation) and X-Server-Time-Ms (standardise +
     model). Their differences attribute the remainder to transport and the
     ASGI server.

    python breakdown.py            # writes experiments/results_v3/S11_serving_breakdown.json

Single host, load generator co-located with the service, as in S9/S10.
"""

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "experiments", "results_v3", "S11_serving_breakdown.json")
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "NUMEXPR_NUM_THREADS")


def stats_ms(ns):
    ms = sorted(v / 1e6 for v in ns)
    k = lambda p: ms[min(len(ms) - 1, int(round((len(ms) - 1) * p)))]
    return {"n": len(ms), "mean": statistics.fmean(ms), "p50": k(0.50),
            "p95": k(0.95), "p99": k(0.99)}


# --------------------------------------------------------------------------
def inproc(iters=3000, warm=200):
    sys.path.insert(0, HERE)
    import numpy as np
    import app as svc

    svc._load()
    feats = svc.STATE["features"]
    with open(os.path.join(svc.ART, "sample_flows.json"), encoding="utf-8") as fh:
        flows = [[float(r[f]) for f in feats] for r in json.load(fh)]
    bodies = [json.dumps({"features": f}).encode() for f in flows]
    model = svc.STATE["model"]
    parse = (svc.Flow.model_validate_json if hasattr(svc.Flow, "model_validate_json")
             else svc.Flow.parse_raw)

    t = {k: [] for k in ("parse_validate", "standardise", "model_one_row",
                         "serialise", "handler_total")}
    for i in range(warm + iters):
        b = bodies[i % len(bodies)]
        t0 = time.perf_counter_ns()
        flow = parse(b)
        t1 = time.perf_counter_ns()
        z = ((np.asarray([flow.features], dtype=np.float64) - svc.STATE["mean"])
             / svc.STATE["scale"]).astype(np.float32)
        t2 = time.perf_counter_ns()
        p = float(model.predict_proba(z)[:, 1][0])
        t3 = time.perf_counter_ns()
        out = json.dumps({"attack_probability": p, "prediction": int(p >= 0.5)}).encode()
        t4 = time.perf_counter_ns()
        if i >= warm:
            t["parse_validate"].append(t1 - t0)
            t["standardise"].append(t2 - t1)
            t["model_one_row"].append(t3 - t2)
            t["serialise"].append(t4 - t3)
            t["handler_total"].append(t4 - t0)
    del out

    X = np.asarray(flows, dtype=np.float64)
    Z = ((X - svc.STATE["mean"]) / svc.STATE["scale"]).astype(np.float32)
    model.predict_proba(Z)
    reps = []
    for _ in range(20):
        t0 = time.perf_counter_ns()
        model.predict_proba(Z)
        reps.append((time.perf_counter_ns() - t0) / len(Z))
    res = {k: stats_ms(v) for k, v in t.items()}
    res["model_amortised_per_row_batch"] = {"batch": len(Z), **stats_ms(reps)}
    res["omp_num_threads"] = os.environ.get("OMP_NUM_THREADS", "default")
    print(json.dumps(res))


# --------------------------------------------------------------------------
async def http_level(url, duration, warmup):
    import httpx
    async with httpx.AsyncClient(base_url=url, timeout=30.0) as c:
        meta = (await c.get("/meta")).json()
        with open(os.path.join(HERE, "artifacts", "sample_flows.json"),
                  encoding="utf-8") as fh:
            flows = [[float(r[f]) for f in meta["features"]] for r in json.load(fh)]
        e2e, total, server = [], [], []
        i = 0
        warm_until = time.perf_counter() + warmup
        stop = warm_until + duration
        while time.perf_counter() < stop:
            body = {"features": flows[i % len(flows)]}
            i += 1
            t0 = time.perf_counter_ns()
            r = await c.post("/predict", json=body)
            dt = time.perf_counter_ns() - t0
            if r.status_code == 200 and time.perf_counter() >= warm_until:
                e2e.append(dt)
                total.append(float(r.headers["X-Total-Time-Ms"]) * 1e6)
                server.append(float(r.headers["X-Server-Time-Ms"]) * 1e6)
    return {"end_to_end": stats_ms(e2e), "app_total": stats_ms(total),
            "model_and_standardise": stats_ms(server)}


def wait_ready(url, proc, timeout=180):
    import urllib.request
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError("service exited")
        try:
            with urllib.request.urlopen(url + "/readyz", timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.05)
    raise TimeoutError("service never became ready")


def env_for(pinned):
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    for v in THREAD_VARS:
        env.pop(v, None)
        if pinned:
            env[v] = "1"
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inproc-child", action="store_true")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--warmup", type=float, default=5.0)
    args = ap.parse_args()
    if args.inproc_child:
        inproc()
        return

    blob = {"host_note": ("single host; load generator co-located; one "
                          "closed-loop client, so no queueing"),
            "settings": {}}
    for label, pinned in (("default_threads", False), ("pinned_one_thread", True)):
        env = env_for(pinned)
        r = subprocess.run([sys.executable, __file__, "--inproc-child"], cwd=HERE,
                           env=env, capture_output=True, text=True, check=True)
        ip = json.loads(r.stdout.strip().splitlines()[-1])
        url = f"http://127.0.0.1:{args.port}"
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
             "--port", str(args.port), "--workers", "1", "--log-level", "warning"],
            cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            wait_ready(url, proc)
            hp = asyncio.run(http_level(url, args.duration, args.warmup))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        for stat in ("p50", "mean"):
            v = {k: hp[k][stat] for k in ("end_to_end", "app_total",
                                           "model_and_standardise")}
            hp[f"attribution_{stat}_ms"] = {
                "model_and_standardise": v["model_and_standardise"],
                "framework_parse_validate_serialise":
                    v["app_total"] - v["model_and_standardise"],
                "transport_and_asgi_server": v["end_to_end"] - v["app_total"],
            }
        blob["settings"][label] = {"in_process": ip, "http_c1": hp}
        print(label, json.dumps(hp["attribution_mean_ms"]),
              "model_one_row p50", ip["model_one_row"]["p50"],
              "amortised", ip["model_amortised_per_row_batch"]["p50"])
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, indent=2)
    print(f"[saved] {OUT}")


if __name__ == "__main__":
    main()
