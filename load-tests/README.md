# Load Tests — Redirect Hot Path

The repo has no other load/soak testing; this is the first. It targets the one
path that is product-critical and burst-prone: `GET /{short_code}` (the
redirect), where a viral link can bring the full internet at once.

## What it does

`locustfile.py` hammers **real short codes** with a realistic traffic mix:

- **80% hot / 20% cold** by default (`HOT_WEIGHT=0.8`) — most requests hit a
  few codes, matching the Pareto-ish share of real redirects.
- Measures the **302** itself (`allow_redirects=False`) — it does not follow
  the redirect and fetch the destination page.
- Fails loudly on anything that is not a 302: a 404/410 (deleted or wrong
  code), a 429 (rate limiter firing, with the `Retry-After` it sent), or any
  other status.
- A `SpikeShape` for the viral moment: ramp to N users in 10s, hold 60s, stop.

The middleware and the redirect handler both rate-limit **per client IP**, and
locust runs every virtual user from one address — so use enough users to be
meaningful (`--users 100`+), and read the 429 rate as the per-IP budget being
hit, not a platform-wide limit.

## Prerequisites

1. A running deployment with a handful of short codes that exist.
   The redirect host is the **backend** (Render), not the frontend:
   `--host https://<your-backend-host>`.

2. Create 20-50 real links first. Quickest via the API:

   ```bash
   # register + login once, then create links with explicit aliases
   curl -s -X POST $HOST/api/v1/auth/register -H 'Content-Type: application/json' \
     -d '{"email":"loadtest@example.com","password":"loadtest123"}'
   curl -s -X POST $HOST/api/v1/auth/login ...   # capture access token
   for i in $(seq 1 50); do
     curl -s -X POST $HOST/api/v1/urls -H "Authorization: Bearer $TOKEN" \
       -H 'Content-Type: application/json' \
       -d "{\"original_url\":\"https://example.com/page/$i\",\"custom_alias\":\"lt$i\"}"
   done
   ```

3. Export the codes and run:

   ```bash
   export SHORT_CODES=lt1,lt2,lt3,...   # at least a handful; add HOT_CODES=lt1,lt2 for the hot set
   uvx locust -f load-tests/locustfile.py \
       --host https://<your-backend-host> \
       --users 200 --spawn-rate 20 --run-time 5m \
       --headless --html load-tests/report.html
   ```

Interactive web UI (opens at http://0.0.0.0:8089): drop `--headless`.

## Spike run

```bash
SHORT_CODES=lt1,lt2,lt3 uvx locust -f load-tests/locustfile.py \
    --host https://<your-backend-host> \
    --shape-class SpikeShape --headless --html load-tests/report.html
```

## What to look at

- **RPS and p95/p99 latency** on `redirect:hot` vs `redirect:cold` — the L1
  cache should keep hot codes off the 100-200ms Upstash REST round trip.
- **Failure counts**: a rising 429 count while users are still under `--users`
  means server-side limits are the bottleneck; a 404 means the codes do not
  exist on the target host.
- **`Retry-After` values** on 429s — they should be present on every 429.
- Run the spike shape against a freshly-invalidated code (disable + re-enable a
  hot link while at peak) to exercise the singleflight coalescing.

## Notes

- Locust is run via `uvx` — no dependency added to `backend/pyproject.toml`;
  the scripts are dev/ops artifacts, not part of the shipped wheel.
- Iterate against a staging deployment before pointing this at production.
  This test will put real load on the target.