import csv
import io
import json
import zipfile
from datetime import datetime, timezone

import qrcode

from src.links.models.tag import Tag
from src.links.models.url import URL, URLStatus
from src.links.repositories.folder_repository import FolderRepository
from src.links.repositories.tag_repository import TagRepository
from src.links.repositories.url_repository import URLRepository
from src.links.services.url_service import RESERVED_ALIASES
from src.shared.core.config import settings
from src.shared.core.redis import delete_url_cache
from src.shared.core.security import hash_password
from src.shared.errors import BadRequestError, FolderNotInWorkspace, NotFoundError, RoleTooLow, WorkspaceNotFound
from src.workspaces.models.workspace_member import MemberRole
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class BulkService:
    def __init__(
        self,
        url_repo: URLRepository,
        folder_repo: FolderRepository,
        tag_repo: TagRepository,
        workspace_repo: WorkspaceRepository,
    ):
        self.url_repo = url_repo
        self.folder_repo = folder_repo
        self.tag_repo = tag_repo
        self.workspace_repo = workspace_repo

    async def _verify_workspace(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()

    async def _verify_write_role(self, workspace_id: int, user_id: int):
        if not await self.workspace_repo.verify_role(workspace_id, user_id, MemberRole.editor):
            raise RoleTooLow("editor")

    async def _resolve_folder(self, folder_id_str: str | None, workspace_id: int) -> int | None:
        if not folder_id_str:
            return None
        try:
            fid = int(folder_id_str.strip())
        except (ValueError, TypeError):
            return None
        if not await self.folder_repo.folder_belongs_to_workspace(fid, workspace_id):
            raise FolderNotInWorkspace()
        return fid

    async def _resolve_tags(self, tags_str: str | None, workspace_id: int) -> list[Tag]:
        if not tags_str:
            return []
        names = [t.strip().lower() for t in tags_str.split(",") if t.strip()]
        tags = []
        for name in set(names):
            tag = await self.tag_repo.get_or_create(name, workspace_id)
            tags.append(tag)
        return tags

    async def create_from_csv(self, workspace_id: int, user_id: int, contents: bytes):
        await self._verify_workspace(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        try:
            reader = csv.DictReader(io.StringIO(contents.decode("utf-8")))
        except Exception:
            raise BadRequestError("Invalid CSV file.")
        created: list[str] = []
        errors: list[dict[str, object]] = []
        for i, row in enumerate(reader, start=2):
            await self._process_row(row, i, workspace_id, user_id, errors, created)
        await self.url_repo.commit()
        return {"created": len(created), "errors": errors, "short_codes": created}

    async def _process_row(self, row: dict, row_num: int, workspace_id: int, user_id: int, errors: list, created: list) -> str | None:
        original_url = row.get("original_url", "").strip()
        if not original_url:
            errors.append({"row": row_num, "error": "Missing original_url"})
            return None

        custom_alias = row.get("custom_alias", "").strip() or None
        if custom_alias and custom_alias in RESERVED_ALIASES:
            errors.append({"row": row_num, "error": f"Alias '{custom_alias}' is reserved"})
            return None

        short_code = custom_alias
        if not short_code:
            short_code = await self.url_repo.next_short_code()

        try:
            try:
                folder_id = await self._resolve_folder(row.get("folder_id"), workspace_id)
            except FolderNotInWorkspace:
                raise ValueError("Folder does not belong to workspace")

            tags = await self._resolve_tags(row.get("tags"), workspace_id)

            expires_at = None
            exp_str = row.get("expires_at", "").strip()
            if exp_str:
                try:
                    expires_at = datetime.fromisoformat(exp_str)
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    raise ValueError(f"Invalid expires_at: {exp_str}")

            password_hash = hash_password(row.get("password", "").strip()) if row.get("password", "").strip() else None

            domain = row.get("domain", "").strip() or None

            is_ab_test = row.get("is_ab_test", "").strip().lower() in ("true", "1", "yes")
            is_one_time = row.get("is_one_time", "").strip().lower() in ("true", "1", "yes")

            ios_url = row.get("ios_url", "").strip() or None
            android_url = row.get("android_url", "").strip() or None

            url = URL(
                short_code=short_code, original_url=original_url,
                user_id=user_id, workspace_id=workspace_id,
                custom_alias=custom_alias, folder_id=folder_id,
                domain=domain,
                password_hash=password_hash,
                expires_at=expires_at, status=URLStatus.active,
                is_ab_test=is_ab_test, is_one_time=is_one_time,
                ios_url=ios_url, android_url=android_url,
            )
            if tags:
                url.tags = tags
            await self.url_repo.add_nested(url)
            created.append(short_code)
        except Exception as e:
            errors.append({"row": row_num, "error": str(e)})
        return short_code

    async def update(self, workspace_id: int, user_id: int, url_ids: list[int], **kwargs):
        await self._verify_workspace(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        if not kwargs:
            raise BadRequestError("No update fields provided.")
        await self.url_repo.bulk_update(url_ids, workspace_id, **kwargs)

    async def disable(self, workspace_id: int, user_id: int, url_ids: list[int]):
        await self._verify_workspace(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        rows = await self.url_repo.get_short_codes_by_ids(url_ids, workspace_id)
        await self.url_repo.bulk_update(url_ids, workspace_id, status=URLStatus.disabled)
        for row in rows:
            await delete_url_cache(row[1])
        return len(rows)

    async def reactivate(self, workspace_id: int, user_id: int, url_ids: list[int]):
        await self._verify_workspace(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        await self.url_repo.reactivate(url_ids, workspace_id)
        return len(url_ids)

    async def delete(self, workspace_id: int, user_id: int, url_ids: list[int]):
        await self._verify_workspace(workspace_id, user_id)
        await self._verify_write_role(workspace_id, user_id)
        rows = await self.url_repo.get_short_codes_by_ids(url_ids, workspace_id)
        await self.url_repo.bulk_update(url_ids, workspace_id, status=URLStatus.deleted)
        for row in rows:
            await delete_url_cache(row[1])
        return len(rows)

    async def export(self, workspace_id: int, user_id: int, fmt: str):
        await self._verify_workspace(workspace_id, user_id)
        result = await self.url_repo.get_workspace_urls(workspace_id)
        urls: list[URL] = result["items"]  # type: ignore[assignment]
        data = [
            {
                "id": u.id, "short_code": u.short_code, "original_url": u.original_url,
                "custom_alias": u.custom_alias or "",
                "expires_at": u.expires_at.isoformat() if u.expires_at else "",
                "created_at": u.created_at.isoformat(),
            }
            for u in urls
        ]
        if fmt == "json":
            return json.dumps(data, indent=2), "application/json", "urls_export.json"
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "short_code", "original_url", "custom_alias", "expires_at", "created_at"])
        writer.writeheader()
        for d in data:
            writer.writerow(d)
        output.seek(0)
        return output.read(), "text/csv", "urls_export.csv"

    async def generate_qr_zip(self, workspace_id: int, user_id: int, url_ids: list[int] | None):
        await self._verify_workspace(workspace_id, user_id)
        result = await self.url_repo.get_workspace_urls(workspace_id)
        urls: list[URL] = result["items"]  # type: ignore[assignment]
        if url_ids:
            urls = [u for u in urls if u.id in url_ids]
        if not urls:
            raise NotFoundError("No URLs found for QR generation.")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for u in urls:
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                base = settings.FRONTEND_URL or "http://localhost:3000"
                qr.add_data(f"{base}/{u.short_code}")
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")  # type: ignore[call-arg]
                buf.seek(0)
                zf.writestr(f"{u.short_code}.png", buf.read())
        zip_buffer.seek(0)
        return zip_buffer
