"""
Closed-loop load generator for the IDS inference service.

Reviewer 1 (concern 9) objected that the deployment section described an
architecture without measuring it, and reviewer 2 (concern 2) objected to a
throughput figure extrapolated from per-sample model cost. This script
produces the missing measurement: real HTTP requests against the running
service, at several concurrency levels, reporting the latency distribution
rather than a single mean.

Design choices that matter for the paper:
  * closed loop -- N clients each send the next request as soon as the
    previous one returns, which is what a bounded worker pool does;
  * a warm-up phase per level whose samples are discarded;
  * the payloads are real held-out CICIDS2017 flows, replayed round-robin;
  * both the end-to-end latency and the server-reported processing time are
    recorded, so queueing can be separated from model cost;
  * a batch-size sweep, because per-record and amortised serving are
    different operating points and the paper must not conflate them.

Usage:
    python bench.py --url http://127.0.0.1:8000 \
        --concurrency 1,8,32,128 --duration 20 --out ../../experiments/results_v3/S9_serving.json
"""

import argparse
import asyncio
import json
import os
import statistics
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ART = os.path.join(os.path.dirname(HERE), "artifacts")


def percentiles(values, points=(50, 90, 95, 99, 99.9)):
    if not values:
        return {}
    s = sorted(values)
    out = {}
    for p in points:
        k = (len(s) - 1) * p / 100.0
        lo, hi = int(k), min(int(k) + 1, len(s) - 1)
        out[f"p{p:g}"] = s[lo] + (s[hi] - s[lo]) * (k - lo)
    return out


def load_flows(art_dir, feature_names):
    with open(os.path.join(art_dir, "sample_flows.json"), encoding="utf-8") as fh:
        records = json.load(fh)
    return [[float(r[f]) for f in feature_names] for r in records]


async def _worker(client, url, payloads, idx, stop_at, lat, srv, errors, warm):
    i = idx
    while time.perf_counter() < stop_at:
        body = payloads[i % len(payloads)]
        i += 1
        t0 = time.perf_counter()
        try:
            r = await client.post(url, json=body)
            dt = 1000 * (time.perf_counter() - t0)
            if r.status_code != 200:
                errors.append(r.status_code)
                continue
            if time.perf_counter() >= warm:
                lat.append(dt)
                h = r.headers.get("X-Server-Time-Ms")
                if h:
                    srv.append(float(h))
        except Exception as exc:            # transport failure counts as error
            errors.append(str(type(exc).__name__))


async def run_level(base, path, payloads, concurrency, duration, warmup):
    lat, srv, errors = [], [], []
    limits = httpx.Limits(max_connections=concurrency + 16,
                          max_keepalive_connections=concurrency + 16)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(base_url=base, limits=limits,
                                 timeout=timeout) as client:
        now = time.perf_counter()
        warm_until = now + warmup
        stop_at = warm_until + duration
        await asyncio.gather(*[
            _worker(client, path, payloads, k, stop_at, lat, srv, errors,
                    warm_until)
            for k in range(concurrency)])

    n = len(lat)
    res = {
        "concurrency": concurrency,
        "requests_measured": n,
        "errors": len(errors),
        "error_kinds": sorted(set(map(str, errors)))[:5],
        "duration_s": duration,
        "throughput_rps": n / duration if duration else 0.0,
        "latency_ms": {
            "mean": statistics.fmean(lat) if lat else None,
            "stdev": statistics.pstdev(lat) if n > 1 else 0.0,
            "min": min(lat) if lat else None,
            "max": max(lat) if lat else None,
            **percentiles(lat),
        },
        "server_time_ms": {
            "mean": statistics.fmean(srv) if srv else None,
            **percentiles(srv),
        },
    }
    print(f"  c={concurrency:<4d} rps={res['throughput_rps']:9.1f} "
          f"p50={res['latency_ms'].get('p50', 0):7.2f} "
          f"p95={res['latency_ms'].get('p95', 0):7.2f} "
          f"p99={res['latency_ms'].get('p99', 0):7.2f} ms  "
          f"errors={len(errors)}")
    return res


async def main_async(args):
    async with httpx.AsyncClient(base_url=args.url, timeout=30.0) as c:
        meta = (await c.get("/meta")).json()
    feature_names = meta["features"]
    flows = load_flows(args.artifacts, feature_names)
    print(f"service: {meta['model']}, {meta['n_features']} features, "
          f"model load {meta['load_seconds']:.3f}s; "
          f"{len(flows)} replay flows")

    out = {"service_meta": meta, "single": [], "batch": []}

    print("\n[single-flow endpoint /predict]")
    for c in [int(x) for x in args.concurrency.split(",")]:
        payloads = [{"features": f} for f in flows]
        out["single"].append(
            await run_level(args.url, "/predict", payloads, c,
                            args.duration, args.warmup))

    print("\n[batch endpoint /predict/batch, concurrency=8]")
    for bs in [int(x) for x in args.batch_sizes.split(",")]:
        payloads = [{"flows": flows[i:i + bs]}
                    for i in range(0, max(1, len(flows) - bs), bs)] or \
                   [{"flows": flows[:bs]}]
        r = await run_level(args.url, "/predict/batch", payloads, 8,
                            args.duration, args.warmup)
        r["batch_size"] = bs
        r["flows_per_s"] = r["throughput_rps"] * bs
        print(f"        batch={bs:<5d} flows/s={r['flows_per_s']:.0f}")
        out["batch"].append(r)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\n[saved] {args.out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--concurrency", default="1,8,32,128")
    ap.add_argument("--batch-sizes", default="1,16,64,256")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--warmup", type=float, default=5.0)
    ap.add_argument("--artifacts", default=DEFAULT_ART)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(HERE)),
        "experiments", "results_v3", "S9_serving.json"))
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
