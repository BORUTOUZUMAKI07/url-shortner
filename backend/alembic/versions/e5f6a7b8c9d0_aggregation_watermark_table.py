"""move the analytics rollup watermark into Postgres

`upsert_rollup` ADDS to `url_analytics_summary.total_clicks`, so a window that
is applied without its cursor advancing is applied again on the next cycle and
the totals inflate permanently. The cursor lived in Redis while the counters
live in Postgres, so no ordering of the two writes was safe: a failure between
them left a partially-applied window that would be re-applied in full.

Storing the cursor in the same database lets the rollup and the cursor commit in
one transaction, which is the only way to make "apply this window" exactly-once
without a dedup key per window.

Redis keeps a copy at `aggregation:last_cutoff` purely as a cache, and the
existing value is seeded here so a deploy does not re-aggregate history.
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

_TABLE = "aggregation_watermarks"
# Same key the worker writes to; matches aggregation_worker._CUTOFF_KEY.
_REDIS_KEY = "aggregation:last_cutoff"
_WATERMARK_KEY = "url_clicked_rollup"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.DateTime(timezone=True), nullable=False),
    )

    # Seed from whatever Redis already holds, so the first cycle after deploy
    # resumes from the existing cursor instead of re-aggregating all history and
    # inflating every total by the full lifetime count.
    try:
        import redis  # noqa: PLC0415 - optional, only present when Redis is reachable

        import src.shared.core.config as cfg

        client = redis.Redis.from_url(cfg.settings.REDIS_URL)
        raw = client.get(_REDIS_KEY)
        if raw:
            op.get_bind().execute(
                sa.text(f"INSERT INTO {_TABLE} (key, value) VALUES (:k, :v) ON CONFLICT DO NOTHING"),
                {
                    "k": _WATERMARK_KEY,
                    "v": raw.decode() if isinstance(raw, bytes) else str(raw),
                },
            )
    except Exception as exc:  # noqa: BLE001 - a missing Redis must not fail the deploy
        print(f"could not seed {_TABLE} from Redis ({exc}); the worker will start fresh")


def downgrade() -> None:
    op.drop_table(_TABLE)
