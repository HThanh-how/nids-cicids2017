"""
Run the whole serving measurement end to end, in one command.

    python run_benchmark.py            # train, serve, measure, shut down

Steps, in order:

  1. Fit and freeze the model, unless artifacts/ already holds one.
  2. Start the service as a separate process, and time the interval between
     process launch and the first successful /readyz -- this is the
     process-level cold start, which is what a pod pays on top of scheduling.
  3. Run the closed-loop load generator over the concurrency and batch-size
     sweeps.
  4. Stop the service and write everything to results_v3/S9_serving.json.

Run this only when the machine is otherwise idle. Latency measured while the
offline experiments are competing for the same cores describes the contention,
not the service.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ART = os.path.join(HERE, "artifacts")
RESULTS = os.path.join(ROOT, "experiments", "results_v3")


def ensure_model():
    if os.path.exists(os.path.join(ART, "model.joblib")):
        print("[1/4] artefact present, skipping training")
        return
    print("[1/4] fitting the serving model")
    subprocess.run([sys.executable, "train_serving_model.py"], cwd=HERE,
                   check=True)


def wait_ready(url, proc, timeout=180):
    """Poll /readyz until it answers 200, and report how long that took."""
    t0 = time.perf_counter()
    last = None
    while time.perf_counter() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"service exited with code {proc.returncode}")
        try:
            with urllib.request.urlopen(url + "/readyz", timeout=2) as r:
                if r.status == 200:
                    return time.perf_counter() - t0, json.loads(
                        r.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = exc
        time.sleep(0.05)
    raise TimeoutError(f"service never became ready ({last})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--concurrency", default="1,8,32,128")
    ap.add_argument("--batch-sizes", default="1,16,64,256")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--warmup", type=float, default=5.0)
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    os.makedirs(RESULTS, exist_ok=True)

    ensure_model()

    print("[2/4] starting the service")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    log = open(os.path.join(HERE, "service.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(args.port), "--workers", "1", "--log-level", "warning"],
        cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        cold_s, ready = wait_ready(url, proc)
        print(f"      ready after {cold_s:.3f}s "
              f"(model load {ready.get('load_seconds', float('nan')):.3f}s)")

        print("[3/4] measuring")
        out = os.path.join(RESULTS, "S9_serving.json")
        subprocess.run(
            [sys.executable, os.path.join("loadtest", "bench.py"),
             "--url", url, "--concurrency", args.concurrency,
             "--batch-sizes", args.batch_sizes,
             "--duration", str(args.duration), "--warmup", str(args.warmup),
             "--out", out], cwd=HERE, check=True)

        # Fold the externally observed cold start into the same file, so the
        # paper's serving section has one source.
        with open(out, encoding="utf-8") as fh:
            blob = json.load(fh)
        blob["cold_start"] = {
            "process_launch_to_ready_s": cold_s,
            "model_load_s": ready.get("load_seconds"),
            "note": ("Measured from process launch to the first successful "
                     "readiness response on this host. Pod scheduling, image "
                     "pull and node-level contention are not included and are "
                     "not measured in this paper."),
        }
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=2)
        print(f"[4/4] wrote {out}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        print("      service stopped")


if __name__ == "__main__":
    main()
