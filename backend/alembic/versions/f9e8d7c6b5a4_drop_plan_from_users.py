"""drop users.plan and the planenum type

Tier/plan removal (see AGENTS.md): users no longer carry a plan, billing is
gone, and the rate-limit/quota tiers collapsed to flat values for everyone.
Postgres enum types can only be dropped once no column uses them, so the
column goes first, then the type. The type is only ever consumed by
users.plan (created in 1fc05da58a8c, extended with 'enterprise' in
c3d4e5f6a7b8), so dropping both is safe.

Revision ID: f9e8d7c6b5a4
Revises: e5f6a7b8c9d0
Create Date: 2026-10-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f9e8d7c6b5a4"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "plan")
    op.execute("DROP TYPE IF EXISTS planenum")


def downgrade() -> None:
    planenum = sa.Enum("free", "premium", "enterprise", name="planenum")
    planenum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("plan", planenum, nullable=False, server_default="free"),
    )