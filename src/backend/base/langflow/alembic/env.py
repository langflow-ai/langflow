import asyncio
import hashlib
import inspect as python_inspect
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from lfx.log.logger import logger
from sqlalchemy import pool, text
from sqlalchemy.event import listen
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from langflow.services.database.models.base import LangflowBaseModel

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
# ---------------------------------------------------------------------------
# Use *isolated* LangflowBaseModel metadata — NOT the global SQLModel.metadata.
# This ensures Alembic autogenerate only sees tables Langflow explicitly owns.
# ---------------------------------------------------------------------------
target_metadata = LangflowBaseModel.metadata
target_metadata.naming_convention = NAMING_CONVENTION

# ---------------------------------------------------------------------------
# Table name whitelist derived from our isolated registry.
# Used by the include_object hook to skip tables from external libraries.
# ---------------------------------------------------------------------------
_langflow_table_names: set[str] | None = None


def _get_langflow_table_names() -> set[str]:
    """Lazily compute the set of table names owned by Langflow."""
    global _langflow_table_names  # noqa: PLW0603
    if _langflow_table_names is None:
        _langflow_table_names = {t.name for t in target_metadata.sorted_tables}
    return _langflow_table_names


def _include_object(object_, name, type_, reflected, compare_to) -> bool:  # noqa: ARG001
    """Alembic ``include_object`` hook.

    Ensures that autogenerate only considers tables registered in
    ``LangflowBaseModel.metadata``.  Tables created by third-party libraries
    (e.g. ``alembic_version``, or any tables registered on the global
    ``SQLModel.metadata``) are silently skipped.
    """
    # Always let non-table objects through (columns, indexes, constraints, etc.)
    if type_ != "table":
        return True

    # For tables: only include if they belong to the Langflow registry
    return name in _get_langflow_table_names()


# ---------------------------------------------------------------------------
# Migration-time sanity check
# ---------------------------------------------------------------------------
def _validate_model_hierarchy() -> None:
    """Abort migration if any ``table=True`` model bypasses ``LangflowBaseModel``.

    Scans the ``langflow.services.database.models`` package for every class
    that:
    * has ``table=True`` (i.e. has a ``__tablename__``)
    * is a subclass of ``SQLModel``

    If such a class is **not** also a subclass of ``LangflowBaseModel``, the
    migration is aborted with a descriptive ``RuntimeError``.

    This acts as a guardrail: developers who forget to use
    ``LangflowBaseModel`` will get an immediate, actionable error during
    ``alembic upgrade`` or ``alembic check``, long before a PR is merged.
    """
    # Import the models package — this triggers all model registrations.
    from langflow.services.database import models

    violations: list[str] = []

    # Walk all members of the models package
    for attr_name in dir(models):
        obj = getattr(models, attr_name, None)
        if obj is None:
            continue
        if not python_inspect.isclass(obj):
            continue
        if not issubclass(obj, SQLModel):
            continue
        # Only care about classes that actually declare a table
        if not getattr(obj, "__tablename__", None):
            continue
        # SQLModel itself has __tablename__ as a class variable — skip it
        if obj is SQLModel or obj is LangflowBaseModel:
            continue
        # The check: every table model must inherit from LangflowBaseModel
        if not issubclass(obj, LangflowBaseModel):
            violations.append(
                f"  • {obj.__module__}.{obj.__qualname__} "
                f"(table={obj.__tablename__!r}) inherits SQLModel but NOT LangflowBaseModel"
            )

    if violations:
        sep = "\n"
        msg = (
            f"\n{'=' * 72}\n"
            f"MIGRATION ABORTED — Model hierarchy violation detected!\n"
            f"{'=' * 72}\n"
            f"The following table model(s) inherit from SQLModel but do NOT\n"
            f"inherit from LangflowBaseModel.  This breaks metadata isolation\n"
            f"and will cause Alembic autogenerate to include foreign tables.\n\n"
            f"{sep.join(violations)}\n\n"
            f"Fix: change the base class to LangflowBaseModel (or a subclass\n"
            f"of LangflowBaseModel) for each model listed above.\n"
            f"{'=' * 72}\n"
        )
        raise RuntimeError(msg)

    logger.info("Model hierarchy validation passed — all table models use LangflowBaseModel.")


# Run the validation immediately when env.py is loaded (i.e., at migration time).
_validate_model_hierarchy()


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
        "include_object": _include_object,
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
        "include_object": _include_object,
    }

    # Only add prepare_threshold for PostgreSQL
    if connection.dialect.name == "postgresql":
        configure_kwargs["prepare_threshold"] = None

    context.configure(**configure_kwargs)
    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            # Use namespace from environment variable if provided, otherwise use default static key
            namespace = os.getenv("LANGFLOW_MIGRATION_LOCK_NAMESPACE")
            if namespace:
                lock_key = int(hashlib.sha256(namespace.encode()).hexdigest()[:16], 16) % (2**63 - 1)
                logger.info(f"Using migration lock namespace: {namespace}, lock_key: {lock_key}")
            else:
                lock_key = 11223344
                logger.info(f"Using default migration lock_key: {lock_key}")

            connection.execute(text("SET LOCAL lock_timeout = '180s';"))
            connection.execute(text(f"SELECT pg_advisory_xact_lock({lock_key});"))
        context.run_migrations()


async def _run_async_migrations() -> None:
    # Disable prepared statements for PostgreSQL (required for PgBouncer compatibility)
    # SQLite doesn't support this parameter, so only add it for PostgreSQL
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
