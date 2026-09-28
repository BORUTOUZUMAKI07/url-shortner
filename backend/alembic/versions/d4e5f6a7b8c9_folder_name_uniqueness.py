"""folder name uniqueness — the one "unique name" with no database enforcement

`FolderService.create` checked `name_exists_in_workspace` and then inserted, as
two separate committed statements. Concurrent creates both passed the read and
both persisted, and both were reported as success. `Tag` has
`uq_tag_name_workspace` for exactly this reason; `Folder` was the outlier.

Reversible: dropping the constraint is all `downgrade` has to do, and the
deduplication is deliberately NOT undone — the rows it removed were
indistinguishable duplicates and re-creating them would need invented data.
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None

_CONSTRAINT = "uq_folder_name_workspace"


def upgrade() -> None:
    bind = op.get_bind()

    # Collapse existing duplicates before adding the constraint. This has to
    # happen first: ADD CONSTRAINT fails outright if the table already violates
    # it, and any database that has seen two concurrent creates already does.
    #
    # Keep the lowest id as the survivor and move its duplicates' URLs across,
    # rather than just deleting the extra rows. `urls.folder_id` is ON DELETE SET
    # NULL, so a bare delete would silently detach those URLs from their folder
    # instead of preserving what the user put there.
    dupes = bind.execute(
        sa.text(
            """
            SELECT f.workspace_id, f.name, MIN(f.id) AS keep_id,
                   ARRAY_AGG(f.id) AS all_ids
            FROM folders f
            GROUP BY f.workspace_id, f.name
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    for row in dupes:
        all_ids = [int(i) for i in row.all_ids]
        keep_id = int(row.keep_id)
        drop_ids = [i for i in all_ids if i != keep_id]
        if not drop_ids:
            continue
        bind.execute(
            sa.text("UPDATE urls SET folder_id = :keep WHERE folder_id = ANY(:drop)"),
            {"keep": keep_id, "drop": drop_ids},
        )
        bind.execute(sa.text("DELETE FROM folders WHERE id = ANY(:drop)"), {"drop": drop_ids})

    op.create_unique_constraint(_CONSTRAINT, "folders", ["name", "workspace_id"])


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "folders", type_="unique")
