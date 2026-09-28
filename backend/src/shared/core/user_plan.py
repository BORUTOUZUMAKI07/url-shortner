import time
from abc import ABC, abstractmethod

from src.identity.models.user import User
from src.shared.core import database

# Short-lived in-process plan cache so premium upgrades take effect without a
# token refresh while avoiding a DB query on every request. The authoritative
# source is always the database.
_USER_PLAN_CACHE_TTL = 60  # seconds
# The value's own TTL never evicts anything, because the miss path overwrites
# the same key. So the dict otherwise retains one entry per user id that has
# ever made an authenticated request, for the life of the process. Prune when it
# crosses this size rather than running a background sweeper.
_MAX_PLAN_CACHE_ENTRIES = 10_000


class UserPlanResolver(ABC):
    @abstractmethod
    async def resolve(self, user_id: int) -> str:
        raise NotImplementedError


class DatabaseUserPlanResolver(UserPlanResolver):
    def __init__(self) -> None:
        self._cache: dict[int, tuple[str, float]] = {}

    async def resolve(self, user_id: int) -> str:
        now = time.time()
        cached = self._cache.get(user_id)
        if cached and cached[1] > now:
            return cached[0]
        # Resolve AsyncSessionLocal at call time (not import time) so the test
        # fixtures that patch `database.AsyncSessionLocal` keep working.
        async with database.AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            plan = user.plan if user else "free"
        if len(self._cache) >= _MAX_PLAN_CACHE_ENTRIES:
            self._prune(now)
        self._cache[user_id] = (plan, now + _USER_PLAN_CACHE_TTL)
        return plan

    def _prune(self, now: float) -> None:
        """Drop every entry whose TTL has passed.

        Only called on write and only at the size threshold, so the common path
        stays a single dict read.
        """
        stale = [uid for uid, (_plan, expires) in self._cache.items() if expires <= now]
        for uid in stale:
            del self._cache[uid]

    def invalidate(self, user_id: int) -> None:
        self._cache.pop(user_id, None)
