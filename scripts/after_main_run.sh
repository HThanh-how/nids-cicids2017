#!/usr/bin/env bash
# Wait for the main experiment to finish, then run the two stages that must
# not compete with it for CPU: the aligned-feature in-domain baseline, and
# the serving load test (which would otherwise measure contention).
set -u
cd "$(dirname "$0")/.."

until grep -q '^Done\.' experiments/run_v3.log 2>/dev/null; do sleep 15; done
echo "=== main run finished ==="

echo "=== S6b: aligned-feature in-domain baseline ==="
( cd experiments && python run_aligned_baseline.py ) 2>&1 | tail -20

echo "=== S9: serving benchmark ==="
( cd serving && python run_benchmark.py ) 2>&1 | tail -40

echo "=== ALL POST-RUN STAGES DONE ==="
