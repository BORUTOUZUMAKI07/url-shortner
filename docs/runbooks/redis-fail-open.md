# Redis Fail-Open

## Symptoms
- Redis health check failing intermittently
- Rate limiting/quota checks degraded (higher burst observed) but app still serving
- Logs show "Redis connection failed" or cache timeouts, no 5xx spike

## Diagnosis
1. **Behavior**: cache lookups, idempotency markers, rate-limit Lua scripts catch Redis exceptions and **fail-open** (treat as miss/allow). This is by design.
2. **Where it hurts**: Upstash REST latency spikes (TLS) can slow requests slightly; in-process L1 cache absorbs redirect reads.
3. **Persistence**: sessions/blacklists use Redis; fail-open on `is_family_revoked` is correct (denylist miss → treat as not revoked, but login/logout paths still set keys). Refresh reuse detection can degrade.
4. **Upstash free tier**: cold connections / regional blips common.

## Mitigation
1. **Don't restart app on transient Redis errors** — logs are warnings, process stays up.
2. **Check Upstash status** (region) or container Redis health (compose).
3. **Scale L1**: redirects benefit most from L1 cache (bounded 8192). Traffic burst → L1 warms.
4. **If persistent (minutes+)**: point `REDIS_URL` to a healthy instance. Render/compose restarts the Redis client on reconnect.
5. **Never force fail-closed** in prod without SLO impact analysis.

## Verification
- App serves redirects/APIs (no 5xx) while Redis degraded.
- After recovery, cache hit rates return to normal, rate limits enforce correctly again.

## Notes
- `TokenRevoked` blacklist cache has 60s TTL with expiration → falls back to authoritative Redis on miss.
- OAuth PKCE/state written atomically via Lua (all-or-nothing). Singleflight protects cold DB misses.
- Quota uses atomic CHECK_AND_INCREMENT_LUA with in-process dict fallback when Redis unavailable.
