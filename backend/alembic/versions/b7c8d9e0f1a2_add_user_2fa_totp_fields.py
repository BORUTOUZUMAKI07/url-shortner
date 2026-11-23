"""add 2FA/TOTP fields to users

Revision ID: b7c8d9e0f1a2
Revises: f9e8d7c6b5a4
Create Date: 2026-11-23

Adds optional TOTP-based two-factor authentication for user accounts.
The secret is stored encrypted at rest; recovery codes are stored as a JSON
array of Argon2 hashes; the last accepted TOTP counter prevents replay within
the validity window.
"""

from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "f9e8d7c6b5a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_last_counter", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("two_factor_recovery_codes", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("two_factor_confirmed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "two_factor_confirmed_at")
    op.drop_column("users", "two_factor_recovery_codes")
    op.drop_column("users", "totp_last_counter")
    op.drop_column("users", "totp_secret_encrypted")
    op.drop_column("users", "two_factor_enabled")
