from src.analytics.schemas.billing import UpgradePlanResponse
from src.identity.models.user import PlanEnum, User
from src.identity.repositories.user_repository import UserRepository
from src.shared.errors import BadRequestError
from src.shared.middleware.rate_limit import invalidate_user_plan_cache


class BillingService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def upgrade_plan(self, user: User, plan: str) -> UpgradePlanResponse:
        plan = plan.lower()
        valid_plans = [p.value for p in PlanEnum]
        if plan not in valid_plans:
            raise BadRequestError(f"Invalid plan '{plan}'. Valid plans: {', '.join(valid_plans)}")
        if plan == user.plan:
            return UpgradePlanResponse(detail=f"You are already on the {plan} plan.", plan=plan)
        await self.repo.update(user.id, plan=PlanEnum(plan))
        invalidate_user_plan_cache(user.id)
        return UpgradePlanResponse(detail=f"Plan upgraded to {plan}.", plan=plan)
