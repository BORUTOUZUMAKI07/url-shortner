import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.links.repositories.url_repository import URLRepository
from src.links.services.utm_service import parse_utm
from src.shared.core.metrics import record_url_redirect
from src.shared.core.redis import check_rate_limit, delete_url_cache, get_url_cache, rate_limit_headers, set_url_cache
from src.shared.core.security import verify_password_async
from src.shared.errors.common import RateLimitError
from src.shared.errors.url import URLDisabled, URLExpired, URLNotFound, URLPasswordIncorrect
from src.shared.events.dispatcher import EventDispatcher
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


@dataclass
class RedirectResult:
    destination: str
    url_id: int
    short_code: str
    workspace_id: int
    is_one_time: bool


# In-flight cold-miss fetches, keyed by short_code. When a cache-bust lands on a
# popular code (delete / bulk-disable / one-time consume), every concurrent miss
# would otherwise run its own DB SELECT against a code that was just invalidated
# — the classic stampede. The first fetch is shared by all waiters instead.
_fetch_inflight: dict[str, asyncio.Task] = {}


def _track_fetch(short_code: str, task: asyncio.Task) -> None:
    def _cleanup(done: asyncio.Task) -> None:
        # Only remove when the dict still points at this task — a newer task may
        # have been registered by a caller that saw us "done" before cleanup ran.
        if _fetch_inflight.get(short_code) is done:
            _fetch_inflight.pop(short_code, None)

    task.add_done_callback(_cleanup)


class RedirectService:
    def __init__(self, url_repo: URLRepository, workspace_repo: WorkspaceRepository, events: EventDispatcher):
        self.url_repo = url_repo
        self.workspace_repo = workspace_repo
        self.events = events

    async def resolve(
        self,
        short_code: str,
        ip: str,
        user_agent: Optional[str],
        referer: Optional[str],
        pwd: Optional[str] = None,
    ) -> RedirectResult:
        rate_result = await check_rate_limit(f"ratelimit:redirect:{short_code}:{ip}", capacity=100, refill_rate_per_sec=1.67)
        if rate_result.limited:
            raise RateLimitError(headers=rate_limit_headers(rate_result, 100))

        url_data, cache_hit = await self._fetch_url(short_code)
        self._validate(url_data)
        await self._check_password(url_data, pwd)
        destination = self._apply_deep_link(url_data, user_agent)
        await self._handle_one_time(url_data)

        utm = parse_utm(url_data["original_url"])

        # Geo resolution is intentionally NOT done here — it is an external HTTP
        # call (ipinfo.io) that would add latency to the redirect hot path. The
        # analytics worker resolves country/city after consuming the event.
        await self.events.dispatch("url-clicked", {
            "event_id": str(uuid.uuid4()),
            "short_code": short_code,
            "original_url": destination,
            "workspace_id": url_data["workspace_id"],
            "ip_address": ip,
            "user_agent": user_agent,
            "referer": referer,
            "utm_source": utm.get("utm_source"),
            "utm_medium": utm.get("utm_medium"),
            "utm_campaign": utm.get("utm_campaign"),
            "clicked_at": datetime.now(timezone.utc).isoformat(),
        }, key=short_code)

        # Count only *served* redirects: anything that raised above (disabled,
        # expired, deleted, wrong password, rate-limited) is not a click.
        record_url_redirect(cache_hit)

        return RedirectResult(
            destination=destination,
            url_id=url_data["id"],
            short_code=short_code,
            workspace_id=url_data["workspace_id"],
            is_one_time=url_data.get("is_one_time", False),
        )

    async def _fetch_url(self, short_code: str) -> tuple[dict, bool]:
        """Return ``(url_data, cache_hit)`` — hit means no DB round trip."""
        url_data = await get_url_cache(short_code)
        if url_data:
            return url_data, True

        # Coalesce concurrent cold misses: one DB fetch serves every waiter.
        # done() tasks are replaced with a fresh fetch; a running one is shared.
        task = _fetch_inflight.get(short_code)
        if task is None or task.done():
            task = asyncio.create_task(self._load_url_and_cache(short_code))
            _fetch_inflight[short_code] = task
            _track_fetch(short_code, task)
        # shield: a cancelled caller must not cancel the shared fetch — that
        # would fail every other in-flight requester with CancelledError. Only
        # the awaiting caller absorbs the cancellation.
        return await asyncio.shield(task), False

    async def _load_url_and_cache(self, short_code: str) -> dict:
        url_obj = await self.url_repo.get_by_short_code(short_code)
        if not url_obj:
            raise URLNotFound()
        url_data = {
            "id": url_obj.id,
            "short_code": url_obj.short_code,
            "original_url": url_obj.original_url,
            "workspace_id": url_obj.workspace_id,
            "is_ab_test": url_obj.is_ab_test,
            "is_one_time": url_obj.is_one_time,
            "ios_url": url_obj.ios_url,
            "android_url": url_obj.android_url,
            "password_hash": url_obj.password_hash,
            "status": url_obj.status.value,
            "expires_at": url_obj.expires_at.isoformat() if url_obj.expires_at else None,
        }
        # Bound the cache TTL to the URL's remaining lifetime so a cached
        # entry never outlives the expiry (otherwise an expired link could
        # keep redirecting until the TTL expires).
        max_ttl = 86400
        if url_obj.expires_at:
            remaining = (url_obj.expires_at - datetime.now(timezone.utc)).total_seconds()
            max_ttl = max(0, min(max_ttl, int(remaining)))
        await set_url_cache(short_code, url_data, ttl=max_ttl)
        return url_data

    def _validate(self, url_data: dict):
        if url_data["status"] == "disabled":
            raise URLDisabled()
        if url_data["status"] == "deleted":
            # A soft-deleted URL must stop serving immediately — the cleanup
            # worker only hard-deletes it later, so without this check a
            # "deleted" link would keep redirecting.
            raise URLNotFound()
        if url_data["expires_at"]:
            expires_at = datetime.fromisoformat(url_data["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                raise URLExpired()

    async def _check_password(self, url_data: dict, pwd: Optional[str]):
        if url_data["password_hash"]:
            if not pwd or not await verify_password_async(pwd, url_data["password_hash"]):
                raise URLPasswordIncorrect()

    def _apply_deep_link(self, url_data: dict, user_agent: Optional[str]) -> str:
        dest = url_data["original_url"]
        if user_agent:
            ua = user_agent.lower()
            if any(d in ua for d in ["iphone", "ipad", "ipod"]) and url_data["ios_url"]:
                dest = url_data["ios_url"]
            elif "android" in ua and url_data["android_url"]:
                dest = url_data["android_url"]
        return dest  # type: ignore[no-any-return]

    async def _handle_one_time(self, url_data: dict):
        if url_data.get("is_one_time"):
            consumed = await self.url_repo.consume_one_time(url_data["id"])
            if consumed == 0:
                # Another request already consumed the link — stop redirecting.
                raise URLNotFound()
            await delete_url_cache(url_data["short_code"])
