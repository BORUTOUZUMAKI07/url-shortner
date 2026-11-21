"""
QRCodeService — Single Responsibility: generate QR codes for URLs.
"""

from src.links.models.url import URLStatus
from src.shared.core.config import settings
from src.shared.core.interfaces import IURLRepository, IWorkspaceRepository


class QRCodeService:
    """Generate QR codes for short URLs. Single responsibility: QR only."""

    def __init__(
        self,
        url_repo: IURLRepository,
        workspace_repo: IWorkspaceRepository,
    ):
        self.url_repo = url_repo
        self.workspace_repo = workspace_repo

    async def generate(
        self, id: int, user_id: int
    ) -> str:
        import base64
        import io

        import qrcode

        url = await self.url_repo.get(id)
        if not url or url.status == URLStatus.deleted:
            raise ValueError("URL not found")

        await self.workspace_repo.verify_access(url.workspace_id, user_id)

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(
            f"{settings.BACKEND_URL or 'http://127.0.0.1:8000'}/{url.short_code}"
        )
        qr.make(fit=True)
        buf = io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        await self.url_repo.update(id, qr_code=b64)
        return b64
