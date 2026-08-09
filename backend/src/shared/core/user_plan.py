import time
from abc import ABC, abstractmethod

from src.identity.models.user import User
from src.shared.core.database import AsyncSessionLocal

# Short-lived in-process plan cache so premium upgrades take effect without a
# token refresh while avoiding a DB query on every request. The authoritative
# source is always the database.
_USER_PLAN_CACHE_TTL = 60  # seconds


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
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            plan = user.plan if user else "free"
        self._cache[user_id] = (plan, now + _USER_PLAN_CACHE_TTL)
        return plan

    def invalidate(self, user_id: int) -> None:
        self._cache.pop(user_id, None)
