// k6 load profile for the IDS inference service.
//
// bench.py is the primary instrument (it needs nothing but Python and runs
// anywhere); this script exists so the measurement can be reproduced with a
// standard tool, and so the cluster run can drive load from outside the
// cluster. Both report the same quantiles.
//
//   k6 run -e BASE=http://<node>:30800 loadtest/k6.js
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://127.0.0.1:8000';
const flows = JSON.parse(open('../artifacts/sample_flows.json'));
const meta = JSON.parse(open('../artifacts/metadata.json'));
const names = meta.selected_features;

const serverTime = new Trend('server_time_ms');

export const options = {
  // A ramping arrival rate: the point of interest is where latency departs
  // from the flat region, which a fixed-rate test cannot show.
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 1 },
        { duration: '30s', target: 8 },
        { duration: '30s', target: 32 },
        { duration: '30s', target: 128 },
        { duration: '15s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<200'],
  },
};

export default function () {
  const row = flows[Math.floor(Math.random() * flows.length)];
  const payload = JSON.stringify({ features: names.map((n) => row[n]) });
  const res = http.post(`${BASE}/predict`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, { 'status 200': (r) => r.status === 200 });
  const st = res.headers['X-Server-Time-Ms'];
  if (st) serverTime.add(parseFloat(st));
}
