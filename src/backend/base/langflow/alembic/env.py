# noqa: INP001
import asyncio
import hashlib
import logging
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.event import listen
from sqlalchemy.ext.asyncio import async_engine_from_config

from langflow.services.database.service import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Configuration constants
SQLITE_BUSY_TIMEOUT_MS = 60000  # 60 seconds
PG_LOCK_TIMEOUT = "60s"
SHA256_BYTES_FOR_KEY = 8

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

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

MAX_I63 = (1 << 63) - 1

def _i63_from_sha256(s: str) -> int:
    """Return a positive 63-bit int from the first 8 bytes of SHA-256(s)."""
    h8 = hashlib.sha256(s.encode("utf-8")).digest()[:SHA256_BYTES_FOR_KEY]  # 64 bits
    return int.from_bytes(h8, "big") & MAX_I63

def _canonical_db_identity(url) -> str:
    """Build a non-sensitive, stable identity string for the target DB/role.

    Avoids password and driver noise, normalizes case and default port.
    """
    # SQLAlchemy URL object
    host = (url.host or "").lower()
    # Normalize default port to 5432 for postgres
    port = url.port or 5432
    dbname = (url.database or "").lower()
    user = (url.username or "").lower()
    # Driver differences (postgresql vs postgresqlpsycopg) should not split identities
    # so we intentionally exclude drivername from the identity.
    return f"{host}:{port}/{dbname}:{user}"

def _compute_lock_key(engine, namespace: str | None) -> int:
    """Compute a transaction advisory lock key.

    base = SHA256(canonical(host,port,db,user)) -> 63-bit
    if namespace: XOR with SHA256(namespace) -> 63-bit
    """
    url = engine.url
    base_key = _i63_from_sha256(_canonical_db_identity(url))
    if namespace:
        ns = namespace.strip().lower()
        if ns:
            ns_key = _i63_from_sha256(ns)
            return (base_key ^ ns_key) & MAX_I63
    return base_key

def _sqlite_do_connect(
    dbapi_connection: Any,
    connection_record: Any,  # noqa: ARG001
):
    # disable pysqlite's emitting of the BEGIN statement entirely.
    # also stops it from emitting COMMIT before any DDL.
    dbapi_connection.isolation_level = None
    # Set busy timeout at connection time to avoid race conditions
    dbapi_connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")

def _sqlite_do_begin(conn):
    # emit our own BEGIN
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
            # Serialize migrations per DB/role, optionally namespaced by env.
            # Optional: LANGFLOW_MIGRATION_LOCK_NAMESPACE (e.g., "blue", "green", "ci")
            namespace = os.getenv("LANGFLOW_MIGRATION_LOCK_NAMESPACE")
            lock_key = _compute_lock_key(connection.engine, namespace)

            # It can be handy for ops to know which namespace is active (no secrets).
            # (Log the namespace string, NOT the computed bigint.)
            if namespace:
                logger.info(
                    "Alembic: using advisory lock namespace=%r (per-DB/role key namespaced)",
                    namespace,
                )
            else:
                logger.warning("Empty LANGFLOW_MIGRATION_LOCK_NAMESPACE, ignoring...")
                logger.info(
                    "Alembic: using advisory lock per-DB/role (no namespace)"
                )

            # Set lock timeout and acquire advisory lock
            connection.exec_driver_sql(f"SET LOCAL lock_timeout = '{PG_LOCK_TIMEOUT}'")
            try:
                connection.exec_driver_sql(f"SELECT pg_advisory_xact_lock({lock_key})")
            except Exception :
                logger.exception("Failed to acquire advisory lock")
                raise

        # Run migrations only once
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

