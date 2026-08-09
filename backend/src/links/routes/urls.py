import base64
import io as _io
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, Query, status

from src.identity.models.user import User
from src.links.models.url import URLStatus
from src.links.schemas.url import URLCreate, URLListResponse, URLResponse, URLUpdate
from src.links.services.url_service import URLService
from src.shared.core.config import settings
from src.shared.core.deps import PaginationParams, get_current_user, get_url_service

router = APIRouter(prefix="/urls", tags=["URLs"])


@router.post("", response_model=URLResponse, status_code=status.HTTP_201_CREATED,
    summary="Create short URL",
    response_description="The newly created shortened URL")
async def create_url(payload: URLCreate, current_user: User = Depends(get_current_user), svc: URLService = Depends(get_url_service)):
    return await svc.create(payload, current_user.id)


@router.get("", response_model=URLListResponse,
    summary="List URLs",
    description="List and search URLs in a workspace with pagination, filtering by folder, tag, status, or free-text search.")
async def list_urls(
    workspace_id: Optional[int] = Query(None, description="Filter by workspace ID"),
    folder_id: Optional[int] = Query(None, description="Filter by folder ID"),
    tag: Optional[str] = Query(None, description="Filter by tag name"),
    search: Optional[str] = Query(None, description="Free-text search in original URL"),
    status_filter: Optional[URLStatus] = Query(None, alias="status", description="Filter by URL status"),
    ids: Optional[str] = Query(None, description="Comma-separated URL IDs to fetch"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    svc: URLService = Depends(get_url_service),
):
    url_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    return await svc.list(workspace_id, current_user.id, folder_id=folder_id, tag=tag, search=search, status_filter=status_filter, url_ids=url_ids, skip=pagination.skip, limit=pagination.limit)


@router.get("/{id}", response_model=URLResponse,
    summary="Get URL details")
async def get_url(id: int, current_user: User = Depends(get_current_user), svc: URLService = Depends(get_url_service)):
    return await svc.get(id, current_user.id)


@router.put("/{id}", response_model=URLResponse,
    summary="Update URL",
    description="Update any field of an existing shortened URL — destination, folder, tags, expiration, etc.")
async def update_url(id: int, payload: URLUpdate, current_user: User = Depends(get_current_user), svc: URLService = Depends(get_url_service)):
    return await svc.update(id, payload, current_user.id)


@router.delete("/{id}",
    summary="Delete URL")
async def delete_url(id: int, current_user: User = Depends(get_current_user), svc: URLService = Depends(get_url_service)):
    await svc.delete(id, current_user.id)
    return {"detail": "URL deleted successfully."}


@router.get("/{id}/qr",
    summary="Get QR code",
    description="Returns the QR code for a short URL as a base64-encoded PNG.")
async def get_qr_code(id: int, current_user: User = Depends(get_current_user), svc: URLService = Depends(get_url_service)):
    url_obj = await svc.get(id, current_user.id)
    if not url_obj.qr_code:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(f"{settings.BACKEND_URL or 'http://127.0.0.1:8000'}/{url_obj.short_code}")
        qr.make(fit=True)
        buf = _io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")  # type: ignore[call-arg]
        b64 = base64.b64encode(buf.getvalue()).decode()
        await svc.update_qr(id, b64, current_user.id)
        url_obj.qr_code = b64
    return {"qr_code": url_obj.qr_code}
