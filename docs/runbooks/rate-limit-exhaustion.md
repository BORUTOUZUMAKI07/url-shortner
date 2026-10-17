# Rate Limit Exhaustion

## Symptoms
- Sudden spike in 429 responses (RateLimit-* headers present)
- Legitimate users report "rate limited" despite normal usage
- Shared bucket (XFF) behavior suspected

## Diagnosis
1. **Headers**: check `Retry-After`, `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` on 429s. Confirms token-bucket.
2. **Client IP resolution**: behind proxies, `X-Forwarded-For` is trusted only if `TRUST_PROXY` is true; we take the **rightmost** entry (edge-appended) — never leftmost. Verify `TRUST_PROXY` matches deployment (Render has proxy).
3. **Keying**: per-IP (all anonymous paths) vs per-user (authenticated). API-key requests also subject to quotas.
4. **Shared proxy**: all users behind a corporate proxy share one IP bucket → exhaustion. Check remote IP distribution in logs.
5. **Auth endpoints**: login/refresh/forgot-password have tighter budgets (anti-bruteforce) — 5/10min etc.

## Mitigation
1. **Don't blindly raise limits**: understand if it's abuse or shared IP.
2. **Whitelist known proxies**: if `TRUST_PROXY` is on, ensure Render's proxy range is trusted (current impl trusts header when flag set; check `client_ip.py`).
3. **Per-user bypass**: authenticated users have higher capacity (100 vs 60). Encourage login if applicable.
4. **Temporary relief**: tune `RATE_LIMIT_*` env vars (capacity/refill) — but affects all users.
5. **Block abusers**: if single IP, consider temporary block at edge (Render doesn't expose IP blocklist easily; app-level 429 is the guard).

## Verification
- 429 rate drops; legitimate traffic returns 200/302.
- `RateLimit-Remaining` stays > 0 for normal clients.
- No increase in 5xx from rate-limit middleware (middleware returns 429 JSON, never crashes).

## Notes
- Middleware returns `JSONResponse` with 429 headers (never raises silently dropping headers).
- Auth rate limits use same client IP resolver.
- The dashboard/API-key quota is a separate daily budget (not the per-request token bucket).
