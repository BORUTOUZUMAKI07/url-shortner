"""add_hotpath_indexes

Adds indexes on columns queried on hot paths but previously unscannable:
- api_keys.prefix        (every API-key auth does a prefix lookup)
- urls.workspace_id      (every URL list/export for a workspace)
- urls.expires_at        (expiry worker scans for expired URLs)
- webhook_events.status  (retry worker scans for failed events)

Revision ID: f5e6d7c8b9a0
Revises: f490c0f533a4
Create Date: 2026-08-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f5e6d7c8b9a0'
down_revision: Union[str, Sequence[str], None] = 'f490c0f533a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_api_keys_prefix', 'api_keys', ['prefix'])
    op.create_index('ix_urls_workspace_id', 'urls', ['workspace_id'])
    op.create_index('ix_urls_expires_at', 'urls', ['expires_at'])
    op.create_index('ix_webhook_events_status', 'webhook_events', ['status'])


def downgrade() -> None:
    op.drop_index('ix_webhook_events_status', table_name='webhook_events')
    op.drop_index('ix_urls_expires_at', table_name='urls')
    op.drop_index('ix_urls_workspace_id', table_name='urls')
    op.drop_index('ix_api_keys_prefix', table_name='api_keys')
