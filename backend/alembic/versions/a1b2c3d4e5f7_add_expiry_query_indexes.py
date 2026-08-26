"""add expiry query indexes

Revision ID: a1b2c3d4e5f7
Revises: f5e6d7c8b9a0
Create Date: 2026-08-26

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "f5e6d7c8b9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Two partial indexes that support the query-time expiry predicate:
    #   WHERE (expires_at IS NULL OR expires_at > now())
    # The planner BitmapOr's these to cover both branches efficiently.
    op.execute(
        "CREATE INDEX ix_urls_workspace_active_no_expiry "
        "ON urls (workspace_id) "
        "WHERE status != 'deleted' AND expires_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_urls_workspace_active_with_expiry "
        "ON urls (workspace_id, expires_at) "
        "WHERE status != 'deleted' AND expires_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_urls_workspace_active_with_expiry", table_name="urls")
    op.drop_index("ix_urls_workspace_active_no_expiry", table_name="urls")
