from typing import List

from fastapi import APIRouter, Depends, status

from src.identity.models.user import User
from src.links.schemas.favorite import FavoriteCreate, FavoriteResponse
from src.links.services.favorite_service import FavoriteService
from src.shared.core.deps import PaginationParams, get_current_user, get_favorite_service

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED,
    summary="Add URL to favorites")
async def add_favorite(payload: FavoriteCreate, current_user: User = Depends(get_current_user), svc: FavoriteService = Depends(get_favorite_service)):
    return await svc.add(payload.url_id, current_user.id)


@router.get("", response_model=List[FavoriteResponse],
    summary="List favorites",
    description="Returns paginated list of the current user's favorite URLs.")
async def list_favorites(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    svc: FavoriteService = Depends(get_favorite_service),
):
    return await svc.list(current_user.id, skip=pagination.skip, limit=pagination.limit)


@router.get("/check/{url_id}",
    summary="Check if URL is favorited")
async def check_favorite(url_id: int, current_user: User = Depends(get_current_user), svc: FavoriteService = Depends(get_favorite_service)):
    is_fav = await svc.check(url_id, current_user.id)
    return {"favorited": is_fav}


@router.delete("/{url_id}",
    summary="Remove from favorites")
async def remove_favorite(url_id: int, current_user: User = Depends(get_current_user), svc: FavoriteService = Depends(get_favorite_service)):
    await svc.remove(url_id, current_user.id)
    return {"detail": "Favorite removed successfully."}
