# noqa: INP001
import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.event import listen
from sqlalchemy.ext.asyncio import async_engine_from_config

from langflow.services.database.service import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata
target_metadata.naming_convention = NAMING_CONVENTION
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
    configure_kwargs = {
        "url": url,
        "target_metadata": target_metadata,
        "literal_binds": True,
        "dialect_opts": {"paramstyle": "named"},
        "render_as_batch": True,
    }

    # Only add prepare_threshold for PostgreSQL
    if url and "postgresql" in url:
        configure_kwargs["prepare_threshold"] = None

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()


def _sqlite_do_connect(
    dbapi_connection,
    connection_record,  # noqa: ARG001
):
    # disable pysqlite's emitting of the BEGIN statement entirely.
    # also stops it from emitting COMMIT before any DDL.
    dbapi_connection.isolation_level = None


def _sqlite_do_begin(conn):
    # emit our own BEGIN
    conn.exec_driver_sql("PRAGMA busy_timeout = 60000")
    conn.exec_driver_sql("BEGIN EXCLUSIVE")


def _do_run_migrations(connection):
    configure_kwargs = {
        "connection": connection,
        "target_metadata": target_metadata,
        "render_as_batch": True,
    }

    # Only add prepare_threshold for PostgreSQL
    if connection.dialect.name == "postgresql":
        configure_kwargs["prepare_threshold"] = None

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET LOCAL lock_timeout = '60s';"))
            connection.execute(text("SELECT pg_advisory_xact_lock(112233);"))
        context.run_migrations()


async def _run_async_migrations() -> None:
    # Get database URL to determine dialect
    url = config.get_main_option("sqlalchemy.url")
    connect_args: dict[str, Any] = {}

    # Only add prepare_threshold for PostgreSQL
    if url and "postgresql" in url:
        connect_args["prepare_threshold"] = None

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    if connectable.dialect.name == "sqlite":
        # See https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
        listen(connectable.sync_engine, "connect", _sqlite_do_connect)
        listen(connectable.sync_engine, "begin", _sqlite_do_begin)

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
