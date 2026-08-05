"""webhook_subscriptions_junction_table

Revision ID: f490c0f533a4
Revises: bf9f68601935
Create Date: 2026-08-05 12:46:46.371343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f490c0f533a4'
down_revision: Union[str, Sequence[str], None] = 'bf9f68601935'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('webhook_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('webhook_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_subscriptions')),
        sa.UniqueConstraint('webhook_id', 'event_type', name='uq_webhook_subscription'),
    )
    op.create_index(op.f('ix_webhook_subscriptions_id'), 'webhook_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_webhook_subscriptions_webhook_id'), 'webhook_subscriptions', ['webhook_id'], unique=False)

    # Migrate existing comma-separated events into junction rows
    op.execute("""
        INSERT INTO webhook_subscriptions (webhook_id, event_type)
        SELECT w.id, trim(unnest(string_to_array(w.events, ',')))
        FROM webhooks w
        WHERE w.events IS NOT NULL AND w.events <> ''
    """)

    op.drop_column('webhooks', 'events')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('webhooks', sa.Column('events', sa.Text(), nullable=True))

    # Rebuild comma-separated events from junction rows
    op.execute("""
        UPDATE webhooks w
        SET events = sub.agg
        FROM (
            SELECT webhook_id, string_agg(event_type, ',') AS agg
            FROM webhook_subscriptions
            GROUP BY webhook_id
        ) sub
        WHERE w.id = sub.webhook_id
    """)

    op.execute("ALTER TABLE webhooks ALTER COLUMN events SET NOT NULL")

    op.drop_index(op.f('ix_webhook_subscriptions_webhook_id'), table_name='webhook_subscriptions')
    op.drop_index(op.f('ix_webhook_subscriptions_id'), table_name='webhook_subscriptions')
    op.drop_table('webhook_subscriptions')
