"""add users.is_active, users.github_id; drop users.role

Revision ID: c8d9e0f1a2b3
Revises: a1b2c3d4e5f7
Create Date: 2026-09-27

is_active: a soft kill switch honoured on every authenticated request
(shared/core/deps.get_current_user already loads the row, so it is free). Until
this, a user could only be removed by a hard delete that cascades their
workspaces, URLs, API keys and audit-log links away with no way back.

github_id: the GitHub provider subject ("sub"). google_id already existed, but
GitHub identities had no column at all, so they could only ever be matched by
email - a mutable, provider-controlled value. See the oauth_callback rewrite.

drop role: users.role had zero readers. Workspace authorisation runs through
workspace_members.role (WorkspaceRepository.verify_role), so the column was
pure dead weight, and surfacing it in the profile/admin UI as "Role" was
actively misleading.
"""

from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.add_column("users", sa.Column("github_id", sa.String(), nullable=True))
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)

    op.drop_column("users", "role")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("owner", "admin", "editor", "viewer", name="roleenum"), nullable=False),
    )
    # Restore the historical default for every row; the values were never read.
    op.execute("UPDATE users SET role = 'owner'")

    op.drop_index("ix_users_github_id", table_name="users")
    op.drop_column("users", "github_id")

    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_column("users", "is_active")
