from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.core.base import Base


class Folder(Base):
    __tablename__ = "folders"
    # Folders had no database-level uniqueness at all, unlike Tag. The service's
    # `name_exists_in_workspace` check is a read followed by a separate insert,
    # so two concurrent creates both passed it and both persisted, and the
    # endpoint reported success for both. A CHECK_AND_CONFLICT is not an option
    # here — the constraint is the only thing that actually makes this unique.
    __table_args__ = (
        UniqueConstraint("name", "workspace_id", name="uq_folder_name_workspace"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    workspace = relationship("Workspace", back_populates="folders")
    urls = relationship("URL", back_populates="folder")
