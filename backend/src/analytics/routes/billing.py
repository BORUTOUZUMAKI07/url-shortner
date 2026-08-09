from fastapi import APIRouter, Depends

from src.analytics.schemas.billing import UpgradePlanRequest, UpgradePlanResponse
from src.analytics.services.billing_service import BillingService
from src.identity.models.user import User
from src.shared.core.deps import get_billing_service, get_current_user

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post("/upgrade", response_model=UpgradePlanResponse, summary="Upgrade or downgrade plan")
async def upgrade_plan(
    payload: UpgradePlanRequest,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return await service.upgrade_plan(current_user, payload.plan)
