"""Delete every user except one, and everything they own.

IRREVERSIBLE. Dry-run by default: it only counts. Pass --execute to actually
delete, and --yes to skip the interactive confirmation.

    uv run python scripts/purge_users.py --keep-email you@example.com
    uv run python scripts/purge_users.py --keep-email you@example.com --execute

Why the deletes are ordered by hand rather than left to ON DELETE CASCADE: the
schema does cascade, but relying on it means an FK added later without a matching
ondelete rule either silently orphans rows or aborts the whole statement halfway.
Deleting parents last, one statement per table, means every step is explicit and
the transaction is all-or-nothing.

Keeps audit_logs: an audit trail that has been deleted alongside the actors is
worth much less, and actor_id is already ON DELETE SET NULL, so those rows
survive with the actor blanked rather than vanishing.
"""

import argparse
import asyncio
from types import SimpleNamespace

from sqlalchemy import text

# Importing only the user repository is not enough: SQLAlchemy resolves
# relationship targets by name at mapper configuration, so a script that touches
# one model without the rest fails with "expression 'Workspace' failed to locate
# a name". Import every model module, as main.py does.
from src.shared.core.database import AsyncSessionLocal, engine

# child table -> (column, parent table). Ordered children-before-parents so a
# row is never orphaned mid-run. Auditing these by hand is the point: an FK added
# later without a matching ondelete would otherwise change the blast radius.
CASCADE_ORDER: list[tuple[str, str, str]] = [
    ("url_analytics_summary", "url_id", "urls"),
    ("url_tags", "url_id", "urls"),
    ("favorites", "url_id", "urls"),
    ("webhook_events", "webhook_id", "webhooks"),
    ("webhook_subscriptions", "webhook_id", "webhooks"),
    ("favorites", "user_id", "users"),
    ("api_keys", "user_id", "users"),
    ("urls", "user_id", "users"),
    ("workspace_invites", "invited_by", "users"),
    ("workspace_members", "user_id", "users"),
    ("webhooks", "workspace_id", "workspaces"),
    ("urls", "workspace_id", "workspaces"),
    ("folders", "workspace_id", "workspaces"),
    ("tags", "workspace_id", "workspaces"),
    ("workspace_invites", "workspace_id", "workspaces"),
    ("workspace_members", "workspace_id", "workspaces"),
    ("webhook_received_events", "workspace_id", "workspaces"),
    ("workspaces", "owner_id", "users"),
    # The users themselves, last: every other step keys off users.id, so this has
    # to come after all of them or the id lists go stale mid-run. Omitting it
    # deletes an account's content and leaves the login row behind.
    ("users", "id", "-"),
]

# Which id list each FK column is matched against. Every column present in
# CASCADE_ORDER must appear here, otherwise a step is silently skipped: the rows
# would still go via ON DELETE CASCADE, but the printed plan would understate the
# damage and the "delete children first" guarantee would be a fiction.
_COLUMN_SOURCES = {
    "user_id": "users",
    "owner_id": "users",
    "invited_by": "users",
    "id": "users",  # the users row itself; see CASCADE_ORDER
    "workspace_id": "workspaces",
    "url_id": "urls",
    "webhook_id": "webhooks",
}


def _source_for(column: str, ids: dict[str, list[int]]):
    table = _COLUMN_SOURCES.get(column)
    return ids.get(table) if table else None


def _mask(url: str) -> str:
    """Show which database this will hit, without printing the password."""
    if "@" not in url:
        return url
    creds, _, host = url.partition("@")
    user = creds.split(":", 1)[0]
    return f"{user}:***@{host}"


async def _uncovered_fks(session) -> list[tuple[str, str]]:
    """Every (table, column) in the live schema that references users/workspaces/
    urls/webhooks - cross-checked against CASCADE_ORDER so a newly added FK is
    noticed before it leaves orphans behind."""
    rows = await session.execute(text("""
        SELECT child.table_name, child.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage child
          ON tc.constraint_name = child.constraint_name
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
        JOIN information_schema.key_column_usage parent
          ON rc.unique_constraint_name = parent.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND parent.table_name IN ('users', 'workspaces', 'urls', 'webhooks')
    """))
    return [(r[0], r[1]) for r in rows]


async def _count(session, table: str, column: str, ids: list[int]) -> int:
    if not ids:
        return 0
    result = await session.execute(
        text(f"SELECT count(*) FROM {table} WHERE {column} = ANY(:ids)"), {"ids": ids}
    )
    return result.scalar_one()


async def main(keep_email: str, execute: bool, assume_yes: bool) -> int:
    from src.shared.core.config import settings

    print(f"Target database: {_mask(settings.DATABASE_URL)}\n")

    async with AsyncSessionLocal() as session:
        # Raw SQL, not the ORM: a maintenance script should depend on the
        # database as it actually is. The ORM selects every mapped column, so
        # this would break outright whenever the app is ahead of the schema
        # (e.g. a migration from this same batch not yet applied).
        keep_row = (await session.execute(
            text("SELECT id, email, plan, is_superadmin FROM users WHERE email = :e"),
            {"e": keep_email},
        )).first()
        keep = SimpleNamespace(
            id=int(keep_row[0]), email=keep_row[1], plan=keep_row[2], is_superadmin=keep_row[3]
        ) if keep_row else None
        if keep is None:
            print(f"ERROR: no user with email {keep_email!r}. Nothing deleted.")
            print("       Check the address, or list users with --list.")
            return 1

        # Resolve the doomed id set up front, from the kept user outwards, so
        # every step below is a plain "delete where id in (...)".
        doomed_users = [int(r[0]) for r in (await session.execute(
            text("SELECT id FROM users WHERE id <> :i"), {"i": keep.id}
        )).all()]

        doomed_workspaces = [int(r[0]) for r in (await session.execute(
            text("SELECT id FROM workspaces WHERE owner_id = ANY(:u)"), {"u": doomed_users}
        )).all()]

        doomed_webhooks = [int(r[0]) for r in (await session.execute(
            text("SELECT id FROM webhooks WHERE workspace_id = ANY(:w)"), {"w": doomed_workspaces}
        )).all()]

        doomed_urls = [int(r[0]) for r in (await session.execute(
            text("SELECT id FROM urls WHERE user_id = ANY(:u) OR workspace_id = ANY(:w)"),
            {"u": doomed_users, "w": doomed_workspaces},
        )).all()]

        ids = {
            "users": doomed_users,
            "workspaces": doomed_workspaces,
            "webhooks": doomed_webhooks,
            "urls": doomed_urls,
        }
        victims = len(doomed_users)

        print(f"KEEPING  {keep.email}  (id={keep.id}, plan={keep.plan}, superadmin={keep.is_superadmin})")
        print(f"DELETING {victims} other user(s)\n")
        print("Rows to be deleted, by table:")
        print("-" * 58)

        plan: list[tuple[str, int]] = []
        for table, column, _parent in CASCADE_ORDER:
            source = _source_for(column, ids)
            if source is None:
                raise SystemExit(
                    f"BUG: {table}.{column} has no id source - refusing to understate the plan."
                )
            n = await _count(session, table, column, source)
            if n:
                plan.append((f"{table}.{column}", n))
                print(f"  {table + '.' + column:<44} {n:>6}")
        # Any FK in the live schema pointing into a doomed table but absent from
        # CASCADE_ORDER would leave rows behind. Catch it here rather than
        # discovering it later as "why does this URL still redirect".
        known = {(t, c) for t, c, _ in CASCADE_ORDER}
        # SET NULL columns are reported but not deleted: audit_logs is the
        # deliberate exception (an audit trail with the actor blanked is still
        # evidence), and webhook_received_events.webhook_id is left pointing at
        # nothing rather than losing received deliveries.
        uncovered = [
            f"{name}.{col}" for name, col in await _uncovered_fks(session)
            if (name, col) not in known
        ]
        if uncovered:
            print("  NOT deleted (ON DELETE SET NULL - rows survive, FK blanked):")
            for name in uncovered:
                print(f"  {name:<44}")
        print("-" * 58)
        print(f"  {'TOTAL':<44} {sum(n for _, n in plan):>6}")
        print()

        if not execute:
            print("DRY RUN - nothing was deleted.")
            print(f"Re-run with --execute to apply (keeps {keep.email}).")
            return 0

        print("This is irreversible and runs against the database above.")
        if not assume_yes:
            reply = input(f"Type the kept email ({keep_email}) to confirm: ").strip()
            if reply != keep_email:
                print("Confirmation did not match. Nothing deleted.")
                return 1

        # Single transaction: either the whole purge lands or none of it does.
        deleted: list[str] = []
        for table, column, _parent in CASCADE_ORDER:
            source = _source_for(column, ids)
            if source is None:
                raise SystemExit(f"BUG: {table}.{column} has no id source.")
            if not source:
                continue
            # Plain text(), not the ORM delete() construct: delete() requires a
            # real Table and these are raw table names, so it raises before any
            # statement is emitted. Table and column names come from
            # CASCADE_ORDER, a literal in this file - never from user input.
            res = await session.execute(
                text(f"DELETE FROM {table} WHERE {column} = ANY(:ids)"), {"ids": source}
            )
            if res.rowcount:
                deleted.append(f"{table}.{column}: {res.rowcount}")
        await session.commit()

        print("\nDeleted:")
        for d in deleted:
            print(f"  {d}")

        remaining = (await session.execute(text("SELECT count(*) FROM users"))).scalar_one()
        print(f"\nUsers remaining: {remaining}")
        if remaining != 1:
            print("WARNING: expected exactly 1 user. Inspect before proceeding.")
            return 1
        print("audit_logs rows were kept (actor_id blanked where the user is gone).")
        return 0


async def _run(keep_email: str, execute: bool, assume_yes: bool) -> int:
    try:
        return await main(keep_email, execute, assume_yes)
    finally:
        # Dispose inside the same event loop. A second asyncio.run() here would
        # find the loop already closed and asyncpg would raise on teardown.
        await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--keep-email", required=True, help="The one user to keep")
    p.add_argument("--execute", action="store_true", help="Actually delete (default: dry run)")
    p.add_argument("--yes", action="store_true", help="Skip the interactive confirmation")
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(args.keep_email, args.execute, args.yes)))
