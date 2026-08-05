"""add_check_constraints

Revision ID: bf9f68601935
Revises: c0d1e2f3a4b5
Create Date: 2026-08-05 12:45:52.385228

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bf9f68601935'
down_revision: Union[str, Sequence[str], None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # CHECK constraints
    op.create_check_constraint("ck_urls_expires_after_created", "urls",
                               "expires_at IS NULL OR expires_at > created_at")
    op.create_check_constraint("ck_api_keys_expires_after_created", "api_keys",
                               "expires_at IS NULL OR expires_at > created_at")
    op.create_check_constraint("ck_invites_expires_after_created", "workspace_invites",
                               "expires_at > created_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_urls_expires_after_created", "urls")
    op.drop_constraint("ck_api_keys_expires_after_created", "api_keys")
    op.drop_constraint("ck_invites_expires_after_created", "workspace_invites")
