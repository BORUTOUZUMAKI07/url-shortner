import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make sure Python can find the src package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can discover them for autogenerate
from src.shared.core.config import settings  # noqa: E402
from src.shared.core.base import Base  # noqa: E402
from src.identity.models.api_key import APIKey  # noqa: E402, F401
from src.identity.models.user import User  # noqa: E402, F401
from src.links.models.favorite import Favorite  # noqa: E402, F401
from src.links.models.folder import Folder  # noqa: E402, F401
from src.links.models.tag import Tag, UrlTag  # noqa: E402, F401
from src.links.models.url import URL  # noqa: E402, F401
from src.analytics.models.analytics import URLAnalyticsSummary  # noqa: E402, F401
from src.analytics.models.audit_log import AuditLog  # noqa: E402, F401
from src.analytics.models.dead_letter import DeadLetterEvent  # noqa: E402, F401
from src.webhooks.models.webhook import Webhook  # noqa: E402, F401
from src.webhooks.models.webhook_event import WebhookEvent  # noqa: E402, F401
from src.webhooks.models.webhook_received_event import WebhookReceivedEvent  # noqa: E402, F401
from src.webhooks.models.webhook_subscription import WebhookSubscription  # noqa: E402, F401
from src.workspaces.models.workspace import Workspace  # noqa: E402, F401
from src.workspaces.models.workspace_invite import WorkspaceInvite  # noqa: E402, F401
from src.workspaces.models.workspace_member import WorkspaceMember  # noqa: E402, F401

target_metadata = Base.metadata

# Override the sqlalchemy.url with the value from our .env file
config.set_main_option("sqlalchemy.url", settings.ASYNC_DATABASE_URI)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
