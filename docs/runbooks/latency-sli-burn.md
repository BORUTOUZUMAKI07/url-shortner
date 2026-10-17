# Latency SLI Burn

## Symptoms
- `redirect_latency_p95_high`: redirect p95 > 150ms for 5m
- `http_latency_p95_high`: general API p95 > 300ms for 10m

## Diagnosis
1. **Path split**: is it *only* redirects, or all API paths? Redirects hit L1 cache first (in-process, 10s TTL) — L1 hit should be < 5ms; Redis hit adds ~10–50ms; DB miss adds 50–200ms.
2. **Cache hit rate**: look at redirect cache labels `layer=l1|redis` (if recorded). L1 miss storms create parallel DB fetches — singleflight coalesces them.
3. **Cold DB**: Neon compute spins down after idle → first query 1–2s → burns budget quickly. Check DB query latency in New Relic.
4. **Geo/metadata off-path**: geo resolution moved to analytics worker (off redirect path). Verify no regression.
5. **OTel overhead negligible**: instrumentation is cheap; sampling 1.0 → collector tail-samples traces.

## Mitigation
1. **Wait for warm DB** (self-heals) if cold start. Hit `/api/v1/ping` a few times.
2. **Check L1 cache**: a deploy restart clears L1 (max 8192 entries) → cold cache. Expect 1–2 min recovery.
3. **Reduce parallelism**: if under DoS, enforce stricter per-IP/user rate limits (429s protect DB).
4. **Rollback** if a recent code change introduced N+1 or added sync work to redirect path.

## Verification
- p95 drops below thresholds for 2 consecutive minutes.
- Redirects return < 200ms for cached codes (spot-check top 5).
- No 5xx introduced by mitigation.

## Notes
- `http.endpoint` label uses route template (`/{short_code}`) — raw paths never create high-cardinality series.
- DB query metrics use `db.operation` (low-cardinality) only.
