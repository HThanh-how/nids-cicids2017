"""
S10: replica scaling, failure recovery and the resource envelope -- measured
without a Kubernetes cluster.

Three of the properties the paper previously listed as unmeasured do not
actually require a scheduler. They require more than one replica and the
willingness to kill one:

  A. Horizontal scaling. N independent service processes are started on N
     ports and the client round-robins across them, holding the offered load
     per replica constant. This answers "does adding a replica add capacity,
     and what happens to latency" without involving pod placement.
  B. Failure recovery. One replica is killed outright while the load runs. A
     supervisor restarts it, as a Deployment would. We count the requests
     that failed and measure how long throughput takes to return.
  C. Resource envelope. CPU and resident memory per replica at idle and at
     saturation, which is what the Deployment's requests and limits should
     have been derived from -- we asserted them and had never measured them.

What still needs a cluster, and is still reported as unmeasured: image pull,
pod placement and kubelet admission, and the HPA control loop's own sync
delay. Those are properties of the scheduler, not of the service, and this
file does not estimate them.

    python scale_and_fault.py            # writes results_v3/S10_scaling.json

Run on an otherwise idle machine.
"""

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import httpx
import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
SERVING = os.path.dirname(HERE)
ROOT = os.path.dirname(SERVING)
ART = os.path.join(SERVING, "artifacts")
RESULTS = os.path.join(ROOT, "experiments", "results_v3")


# --------------------------------------------------------------------------
class Replica:
    """One service process, restartable in place, as a Deployment would."""

    def __init__(self, port, log_dir, omp_threads=None):
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.log_path = os.path.join(log_dir, f"replica-{port}.log")
        self.proc = None
        self.restarts = 0
        # None leaves the maths libraries at their default, which is to use
        # every core; "1" is what the container image sets. The difference
        # decides whether replication helps at all, so both are measured.
        self.omp_threads = omp_threads

    def start(self):
        log = open(self.log_path, "a", encoding="utf-8")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        if self.omp_threads is not None:
            for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
                env[var] = str(self.omp_threads)
        else:
            for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
                env.pop(var, None)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app",
             "--host", "127.0.0.1", "--port", str(self.port),
             "--workers", "1", "--log-level", "error"],
            cwd=SERVING, env=env, stdout=log, stderr=subprocess.STDOUT)
        self._log = log

    def ready(self, timeout=120):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"replica {self.port} exited "
                                   f"({self.proc.returncode})")
            try:
                with urllib.request.urlopen(self.url + "/readyz",
                                            timeout=2) as r:
                    if r.status == 200:
                        return time.perf_counter() - t0
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                pass
            time.sleep(0.05)
        raise TimeoutError(f"replica {self.port} never became ready")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        try:
            self._log.close()
        except Exception:
            pass

    def usage(self):
        """CPU percent since the previous call, and resident memory in MiB."""
        try:
            p = psutil.Process(self.proc.pid)
            return p.cpu_percent(None), p.memory_info().rss / 2 ** 20
        except (psutil.NoSuchProcess, AttributeError):
            return None, None


def start_fleet(n, base_port, log_dir, omp_threads=None):
    reps = [Replica(base_port + i, log_dir, omp_threads) for i in range(n)]
    for r in reps:
        r.start()
    cold = [r.ready() for r in reps]
    for r in reps:            # prime the CPU counters
        r.usage()
    return reps, cold


def percentiles(values, points=(50, 95, 99)):
    if not values:
        return {}
    s = sorted(values)
    out = {}
    for p in points:
        k = (len(s) - 1) * p / 100.0
        lo, hi = int(k), min(int(k) + 1, len(s) - 1)
        out[f"p{p:g}"] = s[lo] + (s[hi] - s[lo]) * (k - lo)
    return out


# --------------------------------------------------------------------------
async def _client_loop(client, urls, payloads, idx, stop_at, warm_until,
                       lat, errors, per_second):
    i = idx
    while time.perf_counter() < stop_at:
        url = urls[i % len(urls)]
        body = payloads[i % len(payloads)]
        i += 1
        t0 = time.perf_counter()
        try:
            r = await client.post(url + "/predict", json=body)
            dt = 1000 * (time.perf_counter() - t0)
            ok = r.status_code == 200
        except Exception:
            dt, ok = 1000 * (time.perf_counter() - t0), False
        now = time.perf_counter()
        if now >= warm_until:
            bucket = per_second.setdefault(int(now - warm_until), [0, 0])
            bucket[0 if ok else 1] += 1
            if ok:
                lat.append(dt)
            else:
                errors.append(1)


async def drive(urls, payloads, concurrency, duration, warmup,
                on_tick=None):
    lat, errors, per_second = [], [], {}
    limits = httpx.Limits(max_connections=concurrency + 32,
                          max_keepalive_connections=concurrency + 32)
    async with httpx.AsyncClient(limits=limits,
                                 timeout=httpx.Timeout(30.0)) as client:
        now = time.perf_counter()
        warm_until, stop_at = now + warmup, now + warmup + duration
        tasks = [asyncio.create_task(
            _client_loop(client, urls, payloads, k, stop_at, warm_until,
                         lat, errors, per_second))
            for k in range(concurrency)]
        if on_tick:
            tasks.append(asyncio.create_task(on_tick(warm_until, stop_at)))
        await asyncio.gather(*tasks)
    return lat, len(errors), per_second


def load_payloads(feature_names, limit=2000):
    with open(os.path.join(ART, "sample_flows.json"), encoding="utf-8") as fh:
        rows = json.load(fh)[:limit]
    return [{"features": [float(r[f]) for f in feature_names]} for r in rows]


def features():
    with open(os.path.join(ART, "metadata.json"), encoding="utf-8") as fh:
        return json.load(fh)["selected_features"]


# --------------------------------------------------------------------------
def stage_scaling(args, payloads, log_dir, omp_threads, base_port):
    """A. Throughput and latency against replica count, with the offered load
    per replica held constant."""
    out = []
    for n in [int(x) for x in args.replicas.split(",")]:
        reps, cold = start_fleet(n, base_port, log_dir, omp_threads)
        try:
            urls = [r.url for r in reps]
            conc = args.per_replica_clients * n
            idle = [r.usage() for r in reps]
            lat, errs, _ = asyncio.run(
                drive(urls, payloads, conc, args.duration, args.warmup))
            busy = [r.usage() for r in reps]
            rec = {
                "replicas": n,
                "omp_threads": omp_threads,
                "clients": conc,
                "clients_per_replica": args.per_replica_clients,
                "throughput_rps": len(lat) / args.duration,
                "errors": errs,
                "latency_ms": {**percentiles(lat),
                               "mean": statistics.fmean(lat) if lat else None},
                "cold_start_s": {"max": max(cold), "mean": statistics.fmean(cold)},
                "cpu_percent_per_replica_busy": [c for c, _ in busy],
                "rss_mib_per_replica_idle": [m for _, m in idle],
                "rss_mib_per_replica_busy": [m for _, m in busy],
            }
            print(f"  replicas={n:<2d} clients={conc:<4d} "
                  f"rps={rec['throughput_rps']:8.1f} "
                  f"p50={rec['latency_ms'].get('p50', 0):7.2f} "
                  f"p95={rec['latency_ms'].get('p95', 0):8.2f} ms  "
                  f"rss={max(m for _, m in busy):6.1f} MiB/replica "
                  f"errors={errs}")
            out.append(rec)
        finally:
            for r in reps:
                r.stop()
    return out


def stage_fault(args, payloads, log_dir, run_index=0):
    """B. Kill one replica under load; a supervisor restarts it. Count the
    requests lost and measure how long throughput takes to recover."""
    n = args.fault_replicas
    reps, _ = start_fleet(n, args.base_port + 100 + 10 * run_index,
                          log_dir, omp_threads=1)
    victim = reps[-1]
    events = {}

    def supervisor(stop_flag):
        """Restart a replica that exits, as a Deployment controller would."""
        while not stop_flag.is_set():
            if victim.proc.poll() is not None and "kill_at" in events:
                t0 = time.perf_counter()
                victim.start()
                try:
                    victim.ready(timeout=60)
                    events["restart_ready_at"] = time.perf_counter()
                    events["restart_seconds"] = time.perf_counter() - t0
                    victim.restarts += 1
                except Exception as exc:
                    events["restart_error"] = str(exc)
                return
            time.sleep(0.05)

    stop_flag = threading.Event()
    th = threading.Thread(target=supervisor, args=(stop_flag,), daemon=True)
    th.start()

    async def killer(warm_until, stop_at):
        await asyncio.sleep(max(0.0, warm_until + args.kill_after
                                - time.perf_counter()))
        events["kill_at"] = time.perf_counter()
        events["kill_second"] = int(events["kill_at"] - warm_until)
        try:
            psutil.Process(victim.proc.pid).kill()
        except psutil.NoSuchProcess:
            pass
        print(f"  killed replica on port {victim.port} at "
              f"t+{args.kill_after:.0f}s")

    try:
        urls = [r.url for r in reps]
        conc = args.per_replica_clients * n
        lat, errs, per_second = asyncio.run(
            drive(urls, payloads, conc, args.fault_duration, args.warmup,
                  on_tick=killer))
    finally:
        stop_flag.set()
        for r in reps:
            r.stop()

    series = [{"second": k, "ok": v[0], "failed": v[1]}
              for k, v in sorted(per_second.items())]
    kill_s = events.get("kill_second")
    pre = [p["ok"] for p in series if kill_s is not None and p["second"] < kill_s]
    baseline = statistics.fmean(pre) if pre else None

    recovered_at = None
    if baseline and kill_s is not None:
        for p in series:
            if p["second"] > kill_s and p["ok"] >= 0.9 * baseline:
                recovered_at = p["second"]
                break

    rec = {
        "replicas": n,
        "clients": conc,
        "killed_port": victim.port,
        "kill_second": kill_s,
        "failed_requests": errs,
        "total_ok": len(lat),
        "baseline_rps_before_kill": baseline,
        "restart_seconds": events.get("restart_seconds"),
        "throughput_recovered_at_second": recovered_at,
        "seconds_to_recover": (None if recovered_at is None or kill_s is None
                               else recovered_at - kill_s),
        "per_second": series,
        "note": ("One replica of four is killed outright and restarted by a "
                 "supervisor. A Kubernetes Service would additionally remove "
                 "the dead endpoint from rotation; this client does not, so "
                 "the failure count is an upper bound on what a cluster "
                 "would lose."),
    }
    print(f"  failed={errs} of {errs + len(lat)}  "
          f"restart={rec['restart_seconds']}  "
          f"recovered_after={rec['seconds_to_recover']}s")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicas", default="1,2,4,8")
    ap.add_argument("--per-replica-clients", type=int, default=8)
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--warmup", type=float, default=4.0)
    ap.add_argument("--fault-replicas", type=int, default=4)
    ap.add_argument("--fault-duration", type=float, default=30.0)
    ap.add_argument("--kill-after", type=float, default=10.0)
    ap.add_argument("--fault-repeats", type=int, default=3)
    ap.add_argument("--base-port", type=int, default=8100)
    ap.add_argument("--out", default=os.path.join(RESULTS, "S10_scaling.json"))
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    log_dir = os.path.join(SERVING, "replica-logs")
    os.makedirs(log_dir, exist_ok=True)

    names = features()
    payloads = load_payloads(names)
    print(f"{len(payloads)} replay flows, {len(names)} features, "
          f"{psutil.cpu_count()} logical cores")

    print("\n[A1] replica scaling, threads unpinned (library default)")
    scaling_free = stage_scaling(args, payloads, log_dir, None,
                                 args.base_port)
    print("\n[A2] replica scaling, one maths thread per replica "
          "(as the image sets)")
    scaling_pinned = stage_scaling(args, payloads, log_dir, 1,
                                   args.base_port + 200)

    print("\n[B] failure recovery")
    faults = []
    for k in range(args.fault_repeats):
        print(f"  run {k + 1} of {args.fault_repeats}")
        faults.append(stage_fault(args, payloads, log_dir, run_index=k))
    lost = [f["failed_requests"] for f in faults]
    recov = [f["seconds_to_recover"] for f in faults
             if f["seconds_to_recover"] is not None]
    restarts = [f["restart_seconds"] for f in faults
                if f["restart_seconds"] is not None]
    fault = {
        "runs": faults,
        "repeats": args.fault_repeats,
        "failed_requests": {"values": lost,
                            "median": statistics.median(lost),
                            "max": max(lost)},
        "restart_seconds": ({"values": restarts,
                             "median": statistics.median(restarts)}
                            if restarts else None),
        "seconds_to_recover": ({"values": recov,
                                "median": statistics.median(recov),
                                "max": max(recov)} if recov else None),
    }
    print(f"  lost {lost} requests; recovery {recov}s "
          f"(median {fault['seconds_to_recover']['median'] if recov else None})")

    blob = {
        "host": {"logical_cores": psutil.cpu_count(),
                 "total_memory_gib": psutil.virtual_memory().total / 2 ** 30},
        "scaling_threads_unpinned": scaling_free,
        "scaling_threads_pinned": scaling_pinned,
        "fault_recovery": fault,
        "not_measured": ["image pull", "pod placement and kubelet admission",
                         "HPA control-loop sync delay"],
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, indent=2)
    print(f"\n[saved] {args.out}")


if __name__ == "__main__":
    main()
