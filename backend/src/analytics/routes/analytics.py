from fastapi import APIRouter, Depends, Query

from src.analytics.services.analytics_service import AnalyticsService
from src.identity.models.user import User
from src.shared.core.deps import get_analytics_service, get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/{short_code}/summary",
    summary="Get URL analytics summary",
    description="Returns click count, unique visitors, device breakdown, and geo data for a short URL.")
async def get_summary(short_code: str, current_user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    return await svc.get_summary(short_code, current_user.id)


@router.get("/{short_code}/timeseries",
    summary="Get analytics time series",
    description="Daily click counts over the last N days (max 90).")
async def get_timeseries(short_code: str, days: int = Query(7, ge=1, le=90, description="Number of days to look back"), current_user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    return await svc.get_timeseries(short_code, current_user.id, days)


@router.get("/{short_code}/devices",
    summary="Get device/browser/OS/geo breakdown",
    description="Returns browser, OS, device, and geographic breakdown from click data.")
async def get_device_breakdown(short_code: str, current_user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    return await svc.get_device_breakdown(short_code, current_user.id)


@router.get("/{short_code}/utm",
    summary="Get UTM campaign breakdown",
    description="Returns UTM source/medium/campaign breakdown for marketing attribution.")
async def get_utm_breakdown(short_code: str, current_user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    return await svc.get_utm_breakdown(short_code, current_user.id)


@router.get("/{short_code}/referrers",
    summary="Get referer breakdown",
    description="Returns referer URLs that drove clicks.")
async def get_referer_breakdown(short_code: str, current_user: User = Depends(get_current_user), svc: AnalyticsService = Depends(get_analytics_service)):
    return await svc.get_referer_breakdown(short_code, current_user.id)
