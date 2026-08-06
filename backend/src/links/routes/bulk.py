from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from src.identity.models.user import User
from src.links.services.bulk_service import BulkService
from src.shared.core.deps import get_bulk_service, get_current_user

router = APIRouter(prefix="/urls/bulk", tags=["Bulk Operations"])


@router.post("/create", status_code=status.HTTP_201_CREATED,
    summary="Bulk create URLs from CSV",
    description="Upload a CSV file with columns: original_url, custom_alias, folder_id, tags, expires_at.")
async def create_from_csv(
    workspace_id: int = Query(..., description="Target workspace ID"),
    file: UploadFile = File(..., description="CSV file with URL definitions"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    contents = await file.read()
    return await svc.create_from_csv(workspace_id, current_user.id, contents)


@router.post("/update",
    summary="Bulk update URLs",
    description="Apply updates (e.g. expiration date) to multiple URLs at once.")
async def bulk_update(
    workspace_id: int = Query(..., description="Workspace containing the URLs"),
    url_ids: list[int] = Query(..., description="List of URL IDs to update"),
    expires_at: Optional[str] = Query(None, description="New expiration date (ISO 8601 format)"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    kwargs = {}
    if expires_at:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(expires_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        kwargs["expires_at"] = dt
    await svc.update(workspace_id, current_user.id, url_ids, **kwargs)
    return {"updated": len(url_ids)}


@router.post("/disable",
    summary="Bulk disable URLs")
async def bulk_disable(
    workspace_id: int = Query(..., description="Workspace containing the URLs"),
    url_ids: list[int] = Query(..., description="List of URL IDs to disable"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    count = await svc.disable(workspace_id, current_user.id, url_ids)
    return {"disabled": count}


@router.post("/reactivate",
    summary="Bulk reactivate URLs")
async def bulk_reactivate(
    workspace_id: int = Query(..., description="Workspace containing the URLs"),
    url_ids: list[int] = Query(..., description="List of URL IDs to reactivate"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    count = await svc.reactivate(workspace_id, current_user.id, url_ids)
    return {"reactivated": count}


@router.post("/delete",
    summary="Bulk delete URLs")
async def bulk_delete(
    workspace_id: int = Query(..., description="Workspace containing the URLs"),
    url_ids: list[int] = Query(..., description="List of URL IDs to delete"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    count = await svc.delete(workspace_id, current_user.id, url_ids)
    return {"deleted": count}


@router.get("/export",
    summary="Bulk export URLs",
    description="Export all URLs in a workspace as CSV or JSON file.")
async def bulk_export(
    workspace_id: int = Query(..., description="Workspace to export"),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    content, media_type, filename = await svc.export(workspace_id, current_user.id, format)
    return StreamingResponse(
        iter([content.encode() if isinstance(content, str) else content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/qr",
    summary="Bulk generate QR codes",
    description="Generate a ZIP file containing QR code PNGs for multiple URLs.")
async def bulk_qr_zip(
    workspace_id: int = Query(..., description="Workspace containing the URLs"),
    url_ids: Optional[list[int]] = Query(None, description="Specific URL IDs (omit for all)"),
    current_user: User = Depends(get_current_user),
    svc: BulkService = Depends(get_bulk_service),
):
    zip_buffer = await svc.generate_qr_zip(workspace_id, current_user.id, url_ids)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=qr_codes.zip"})
