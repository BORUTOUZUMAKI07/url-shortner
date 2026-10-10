"""Locust load test for the URL-shortener redirect hot path.

The redirect path (`/{short_code}`) is the one product-critical burst risk:
a viral short code can receive the full internet's attention at once. This
scenario hammers real short codes with a realistic traffic mix and treats
non-302/429/404-by-surprise responses as failures.

Run (from the repo root):

    uvx locust -f load-tests/locustfile.py \
        --host https://shrt.your-domain.com \
        --users 200 --spawn-rate 20 --run-time 5m \
        --headless --html load-tests/report.html

Environment:

    SHORT_CODES   comma-separated short codes that exist in the deployment
                  (required — the test refuses to run without them)
    HOT_CODES     subset of SHORT_CODES to hammer as "hot" (default: the
                  first fifth of SHORT_CODES)
    HOT_WEIGHT    probability a request hits a hot code (default 0.8 — a
                  Pareto-ish mix: most traffic, few codes)
    REDIRECT_PATH path prefix if short codes live under one (default "")

Spike run (ramps to N users in 10s, holds 60s, stops):

    SHORT_CODES=abc,def uvx locust -f load-tests/locustfile.py \
        --host https://shrt.your-domain.com \
        --shape-class SpikeShape --headless --html load-tests/report.html

Note: the backend rate-limits per client IP, and locust runs every virtual
user from one address, so a small --users count will trip the limiter and
under-report throughput. Use enough users to be meaningful (>= 100).
"""

import os
import random
from locust import HttpUser, LoadTestShape, between, events, task

SHORT_CODES = [c.strip() for c in os.environ.get("SHORT_CODES", "").split(",") if c.strip()]
HOT_CODES = [c.strip() for c in os.environ.get("HOT_CODES", "").split(",") if c.strip()]
if not HOT_CODES:
    HOT_CODES = SHORT_CODES[: max(1, len(SHORT_CODES) // 5)]
HOT_WEIGHT = float(os.environ.get("HOT_WEIGHT", "0.8"))
REDIRECT_PATH = os.environ.get("REDIRECT_PATH", "").rstrip("/")


@events.test_start.add_listener
def _validate_config(environment, **_kwargs):
    if not SHORT_CODES:
        raise SystemExit(
            "Set SHORT_CODES=code1,code2,... (and optionally HOT_CODES) before running. "
            "The test needs real short codes to redirect."
        )


def _pick_code() -> str:
    if HOT_CODES and random.random() < HOT_WEIGHT:
        return random.choice(HOT_CODES)
    return random.choice(SHORT_CODES)


class RedirectUser(HttpUser):
    """A visitor hitting short-code redirects with a hot/cold mix."""

    wait_time = between(0.05, 0.5)

    @task
    def redirect(self):
        code = _pick_code()
        name = "redirect:hot" if code in HOT_CODES else "redirect:cold"
        with self.client.get(
            f"{REDIRECT_PATH}/{code}",
            name=name,
            allow_redirects=False,  # measure the 302, not the destination page
            catch_response=True,
        ) as resp:
            if resp.status_code == 302:
                resp.success()
            elif resp.status_code in (404, 410):
                resp.failure(f"redirect returned {resp.status_code} for {code}")
            elif resp.status_code == 429:
                resp.failure(
                    f"rate limited (429) — Retry-After={resp.headers.get('Retry-After', '?')}"
                )
            else:
                resp.failure(f"unexpected status {resp.status_code} for {code}")


class SpikeShape(LoadTestShape):
    """Ramp to SPIKE_PEAK_USERS (default 300) within 10s, hold 60s, stop.

    The sudden load reproduces a viral-link moment: the L1 cache warms, then a
    cache-bust (invalidation) while still at peak is the stampede scenario the
    singleflight coalescing was built for.
    """

    peak = int(os.environ.get("SPIKE_PEAK_USERS", "300"))

    def tick(self):
        run_time = self.get_run_time()
        if run_time < 10:
            return (int(self.peak * (run_time + 1) / 10), 30)
        if run_time < 70:
            return (self.peak, 0)
        return None