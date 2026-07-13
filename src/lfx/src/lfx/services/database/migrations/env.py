"""Alembic environment for lfx's own migration stream.

This is lfx's *independent* migration lineage. It stamps a distinct version
table (``lfx_alembic_version``) and, via the ``include_name`` / ``include_object``
filters below, only ever considers the execution-history tables lfx owns
(``LFX_MIGRATION_TABLES``). That is the ownership boundary that keeps this stream
isolated from langflow's 82-migration lineage:

* A langflow-only table (e.g. a future ``authz_*`` table, or a user's own model)
  is invisible here -- the filters skip it -- so it never enters or perturbs
  lfx's lineage.
* An lfx-core table change is visible to *both* streams' autogenerate, so it
  needs a revision in each. ``alembic check`` (run per-stream in CI) fails the
  build the moment a stream lags the shared model, so drift is loud, not silent.

The ``NAMING_CONVENTION`` is intentionally byte-for-byte identical to langflow's
env so the same model yields identically-named indexes/constraints in both
streams -- itself a divergence-prevention measure.
"""

import asyncio
import hashlib
import os
import warnings
from logging.config import fileConfig
from typing import Any

from alembic import context
from lfx.log.logger import logger

# Importing the model modules registers the lfx-core tables on SQLModel.metadata
# so autogenerate can see them. Only lfx-owned execution-history tables are
# imported here; the include filters below are the authoritative boundary.
from lfx.services.database.models import message as _message  # noqa: F401
from lfx.services.database.models import transactions as _transactions  # noqa: F401
from lfx.services.database.models import vertex_builds as _vertex_builds  # noqa: F401
from sqlalchemy import pool, text
from sqlalchemy.event import listen
from sqlalchemy.exc import SAWarning
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

# The tables lfx's migration stream owns. Keep in sync with
# DatabaseService.expected_tables. ``lfx_alembic_version`` is included so alembic
# does not try to drop its own bookkeeping table.
LFX_MIGRATION_TABLES = {
    "message",
    "transaction",
    "vertex_build",
    "lfx_alembic_version",
}

# The version table for lfx's stream -- distinct from langflow's default
# ``alembic_version`` so the two lineages never collide in one database.
LFX_VERSION_TABLE = "lfx_alembic_version"

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

target_metadata = SQLModel.metadata
target_metadata.naming_convention = NAMING_CONVENTION


def include_name(name, type_, parent_names) -> bool:  # noqa: ARG001
    """Restrict reflection to lfx-owned tables.

    Without this, autogenerate reflecting a database that also holds langflow
    tables would propose dropping them. Filtering by name keeps this stream blind
    to everything but the tables it owns.
    """
    if type_ == "table":
        return name in LFX_MIGRATION_TABLES
    return True


def include_object(obj, name, type_, reflected, compare_to) -> bool:  # noqa: ARG001
    """Restrict metadata objects to lfx-owned tables (mirror of include_name)."""
    if type_ == "table":
        return name in LFX_MIGRATION_TABLES
    return True


def _configure_kwargs(base: dict[str, Any]) -> dict[str, Any]:
    base.update(
        {
            "target_metadata": target_metadata,
            "version_table": LFX_VERSION_TABLE,
            "include_name": include_name,
            "include_object": include_object,
            "render_as_batch": True,
        }
    )
    return base


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    configure_kwargs = _configure_kwargs(
        {
            "url": url,
            "literal_binds": True,
            "dialect_opts": {"paramstyle": "named"},
        }
    )
    if url and "postgresql" in url:
        configure_kwargs["prepare_threshold"] = None

    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()


def _sqlite_do_connect(dbapi_connection, connection_record):  # noqa: ARG001
    # disable pysqlite's emitting of the BEGIN statement entirely.
    dbapi_connection.isolation_level = None


def _sqlite_do_begin(conn):
    # emit our own BEGIN
    conn.exec_driver_sql("PRAGMA busy_timeout = 60000")
    conn.exec_driver_sql("BEGIN EXCLUSIVE")


def _do_run_migrations(connection) -> None:
    configure_kwargs = _configure_kwargs({"connection": connection})
    if connection.dialect.name == "postgresql":
        configure_kwargs["prepare_threshold"] = None

    context.configure(**configure_kwargs)
    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            # Serialise concurrent migration runs across workers with an advisory
            # lock so they do not race on CREATE TABLE against a fresh database.
            namespace = os.getenv("LANGFLOW_MIGRATION_LOCK_NAMESPACE")
            if namespace:
                lock_key = int(hashlib.sha256(namespace.encode()).hexdigest()[:16], 16) % (2**63 - 1)
                logger.info(f"Using migration lock namespace: {namespace}, lock_key: {lock_key}")
            else:
                lock_key = 11223344
                logger.info(f"Using default migration lock_key: {lock_key}")

            connection.execute(text("SET LOCAL lock_timeout = '180s';"))
            connection.execute(text(f"SELECT pg_advisory_xact_lock({lock_key});"))
        if connection.dialect.name == "sqlite":
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*SQL-parsed foreign key constraint.*could not be located in PRAGMA foreign_keys.*",
                    category=SAWarning,
                )
                warnings.filterwarnings(
                    "ignore",
                    message=(
                        "autogenerate skipping metadata-specified expression-based index "
                        "'ix_message_session_metadata_(tenant|user)'; dialect 'sqlite'.*"
                    ),
                    category=UserWarning,
                )
                context.run_migrations()
        else:
            context.run_migrations()


async def _run_async_migrations() -> None:
    config_section = config.get_section(config.config_ini_section, {})
    db_url = config_section.get("sqlalchemy.url", "")

    connect_args: dict[str, Any] = {}
    if db_url and "postgresql" in db_url:
        connect_args["prepare_threshold"] = None

    connectable = async_engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    if connectable.dialect.name == "sqlite":
        listen(connectable.sync_engine, "connect", _sqlite_do_connect)
        listen(connectable.sync_engine, "begin", _sqlite_do_begin)

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
