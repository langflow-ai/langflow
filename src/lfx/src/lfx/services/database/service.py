"""Database service implementations for lfx package.

Two implementations live here:

* :class:`NoopDatabaseService` -- the zero-dependency default for bare ``lfx``
  usage; every session is a :class:`~lfx.services.session.NoopSession`.
* :class:`DatabaseService` -- the real Tier 1 infrastructure service: a pooled
  async SQLAlchemy engine plus an alembic migration runner over lfx's own
  migration stream (``lfx.services.database.migrations``, version table
  ``lfx_alembic_version``).

langflow subclasses :class:`DatabaseService` (thin override) to point the
migration runner at its own alembic tree and to add its domain bootstrap
(superuser assignment, schema-health checks). The engine/session/migration
*mechanism* is shared; only the migration-stream identity and domain policy
differ. See ``PLUGGABLE_SERVICES.md`` (two-stream migration model) for why the
two alembic lineages stay isolated.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import time
from contextlib import asynccontextmanager, contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import sqlalchemy as sa
from alembic import command, util
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.dialects import sqlite as dialect_sqlite
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, text
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
from tenacity import retry, stop_after_attempt, wait_fixed

from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.capabilities import Capability, Tier
from lfx.services.database.constants import (
    MIN_POSTGRESQL_MAJOR_VERSION,
    POSTGRESQL_VERSION_REQUIRED_MESSAGE,
)
from lfx.services.deps import session_scope
from lfx.utils.windows_postgres_helper import configure_windows_postgres_event_loop

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

    from lfx.services.settings.service import SettingsService


class NoopDatabaseService:
    """No-operation database service for standalone lfx usage.

    This provides a database service interface that always returns NoopSession,
    allowing lfx to work without a real database connection.

    As a Tier 1 (infrastructure) service it declares no capabilities: a
    ``NoopSession`` neither persists across restarts nor shares state across
    processes. A Tier 2 service that ``Requires`` the database with
    ``{PERSISTENT}`` therefore fails ``validate_wiring()`` against this
    implementation -- which is the desired loud-at-boot behavior instead of
    silent no-op writes.
    """

    # Tier 1 infrastructure port. NoopSession is in-process and ephemeral, so no
    # capability is advertised. (The chat-memory service requires the database to
    # be *present*, not PERSISTENT, so it still wires successfully over this.)
    tier: ClassVar[Tier] = Tier.INFRASTRUCTURE
    capabilities: ClassVar[frozenset[Capability]] = frozenset()

    @asynccontextmanager
    async def _with_session(self):
        """Internal method to create a session. DO NOT USE DIRECTLY.

        Use session_scope() for write operations or session_scope_readonly() for read operations.
        This method does not handle commits - it only provides a raw session.
        """
        from lfx.services.session import NoopSession

        async with NoopSession() as session:
            yield session

    def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Write session scope over this service (auto-commit/rollback).

        Part of the Tier 1 database port: Tier 2 services call this on their
        injected ``database_service`` rather than reaching for a global.
        """
        from lfx.services.database.session import session_scope_for

        return session_scope_for(self)

    def session_scope_readonly(self) -> AsyncGenerator[AsyncSession, None]:
        """Read-only session scope over this service (no commit/rollback)."""
        from lfx.services.database.session import session_scope_readonly_for

        return session_scope_readonly_for(self)


# ---------------------------------------------------------------------------
# Migration + connection helpers (module-level, dialect-aware, pure).
# ---------------------------------------------------------------------------


class UnsupportedPostgreSQLVersionError(Exception):
    """Raised when the PostgreSQL version is below the minimum required."""


_PG_VERSION_QUERY = sa.text("SELECT current_setting('server_version_num'), current_setting('server_version')")

# Stable namespace for the schema-migration advisory lock. The lock serializes
# concurrent ``alembic upgrade`` runs across workers so they do not race to
# CREATE TYPE / CREATE TABLE on a fresh database. Picked once and never changed
# so independent processes converge on the same lock; the value itself is
# arbitrary, just has to fit in a Postgres bigint and not collide with other
# advisory locks the application takes (currently none).
_MIGRATION_ADVISORY_LOCK_ID = 0x4C616E67666C6F77  # ASCII "Langflow"
_MIGRATION_LOCK_DEFAULT_TIMEOUT_S = 300.0
_MIGRATION_LOCK_POLL_INTERVAL_S = 2.0


def _migration_lock_timeout_s() -> float:
    raw = os.getenv("LANGFLOW_MIGRATION_LOCK_TIMEOUT_S")
    if raw is None:
        return _MIGRATION_LOCK_DEFAULT_TIMEOUT_S
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid LANGFLOW_MIGRATION_LOCK_TIMEOUT_S=%r; falling back to %.0fs.",
            raw,
            _MIGRATION_LOCK_DEFAULT_TIMEOUT_S,
        )
        return _MIGRATION_LOCK_DEFAULT_TIMEOUT_S


def _acquire_migration_lock_or_raise(conn, lock_id: int) -> None:
    """Acquire the advisory lock with a bounded wait, logging progress.

    Blocking ``pg_advisory_lock`` has no upper bound and ``lock_timeout`` does
    not apply to advisory locks, so a worker hung mid-migration would silently
    block every other worker forever. Instead poll ``pg_try_advisory_lock`` with
    a configurable timeout and log when we're waiting, so operators see why
    boot is stuck.
    """
    if conn.execute(sa.text(f"SELECT pg_try_advisory_lock({lock_id})")).scalar():
        return

    timeout = _migration_lock_timeout_s()
    logger.info(
        "Migration advisory lock %s held by another worker; waiting up to %.0fs.",
        lock_id,
        timeout,
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(_MIGRATION_LOCK_POLL_INTERVAL_S)
        if conn.execute(sa.text(f"SELECT pg_try_advisory_lock({lock_id})")).scalar():
            logger.info("Acquired migration advisory lock %s after waiting.", lock_id)
            return

    msg = (
        f"Could not acquire migration advisory lock {lock_id} within "
        f"{timeout:.0f}s. Another worker is likely hung mid-migration. "
        "Investigate the worker holding the lock or restart the deployment "
        "with a single worker so migrations can run cleanly. Override the "
        "wait via LANGFLOW_MIGRATION_LOCK_TIMEOUT_S (seconds) if your migration "
        "legitimately needs longer."
    )
    raise RuntimeError(msg)


def _normalize_sync_postgres_url(database_url: str) -> str:
    """Return a sync-driver Postgres URL from a possibly async one.

    Strips the ``+asyncpg`` / ``+aiosqlite`` suffix and upgrades the legacy
    ``postgres://`` scheme to ``postgresql://`` so :func:`sa.create_engine`
    picks the default sync driver. Centralised so the advisory-lock helper and
    the table-creation lock path stay in sync with :func:`check_postgresql_version_sync`.
    """
    sync_url = database_url
    if sync_url.startswith("postgres://"):
        sync_url = "postgresql://" + sync_url.split("://", 1)[1]
    for async_driver in ("+asyncpg", "+aiosqlite"):
        sync_url = sync_url.replace(async_driver, "")
    return sync_url


@contextmanager
def _postgres_migration_lock(database_url: str):
    """Hold a Postgres session-level advisory lock for the duration of the block.

    Workers starting concurrently against a fresh PostgreSQL each call
    ``command.upgrade("head")``; without coordination they race on
    ``CREATE TYPE`` / ``CREATE TABLE`` and the losers fail with
    ``UniqueViolation``. Holding a session-level advisory lock serialises the
    upgrade so only one worker mutates the schema at a time; the others wait
    here (bounded, with progress logging) and then find the schema already at
    head.

    No-op for non-PostgreSQL URLs. SQLite has no advisory locks (and runs
    single-process anyway).
    """
    if not database_url.startswith(("postgresql", "postgres")):
        yield
        return

    engine = sa.create_engine(_normalize_sync_postgres_url(database_url))
    try:
        with engine.connect() as conn:
            logger.debug("Acquiring migration advisory lock %s", _MIGRATION_ADVISORY_LOCK_ID)
            _acquire_migration_lock_or_raise(conn, _MIGRATION_ADVISORY_LOCK_ID)
            try:
                yield
            finally:
                logger.debug("Releasing migration advisory lock %s", _MIGRATION_ADVISORY_LOCK_ID)
                # Session-level locks auto-release on connection close, but
                # explicit unlock keeps the connection reusable if alembic
                # internals ever hand us one back.
                conn.execute(sa.text(f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})"))
    finally:
        engine.dispose()


def _check_version_row(version_num_str: str, version_str: str) -> None:
    """Raise ``UnsupportedPostgreSQLVersionError`` when the version is too old."""
    if int(version_num_str) < MIN_POSTGRESQL_MAJOR_VERSION * 10000:
        msg = f"Running PostgreSQL {version_str}. {POSTGRESQL_VERSION_REQUIRED_MESSAGE}"
        logger.error(msg)
        raise UnsupportedPostgreSQLVersionError(msg)


def check_postgresql_version_sync(database_url: str) -> None:
    """Pre-flight check: verify PostgreSQL >= 15 using a synchronous connection.

    Call this *before* starting uvicorn/gunicorn so a version mismatch
    results in a clean ``sys.exit(1)`` rather than a messy lifespan failure.
    Silently returns when the URL is not PostgreSQL.
    """
    if not database_url.startswith(("postgresql", "postgres")):
        return

    from sqlalchemy import create_engine

    engine = create_engine(_normalize_sync_postgres_url(database_url))
    try:
        with engine.connect() as conn:
            row = conn.execute(_PG_VERSION_QUERY).fetchone()
            _check_version_row(*row)
    finally:
        engine.dispose()


def get_sqlite_database_file_path(database_url: str) -> Path | None:
    """Return the on-disk file path for a SQLite URL, or ``None`` when there is none.

    Returns ``None`` for non-SQLite URLs and for in-memory SQLite databases
    (``sqlite://`` and ``sqlite:///:memory:``), which have no file on disk. The
    returned path is kept exactly as written in the URL (relative paths are *not*
    resolved) so callers can report it back to the user verbatim.
    """
    if not database_url.startswith("sqlite"):
        return None
    try:
        database = make_url(database_url).database
    except Exception:  # noqa: BLE001 - defensive: malformed URLs are handled elsewhere
        return None
    if not database or database == ":memory:":
        return None
    return Path(database)


def to_async_driver_url(database_url: str) -> str:
    """Rewrite a bare dialect URL to its async driver form.

    ``sqlite`` -> ``sqlite+aiosqlite``; ``postgresql`` / ``postgres`` ->
    ``postgresql+psycopg``. Already-qualified drivers pass through unchanged.
    Shared by :meth:`DatabaseService._sanitize_database_url` and the ``lfx db``
    CLI so both drive the same async driver.
    """
    driver, _, rest = database_url.partition("://")
    if not rest:
        return database_url
    if driver == "sqlite":
        driver = "sqlite+aiosqlite"
    elif driver in {"postgresql", "postgres"}:
        driver = "postgresql+psycopg"
    return f"{driver}://{rest}"


def check_sqlite_database_path(database_url: str) -> None:
    """Fail fast with an actionable message when a SQLite database cannot be opened.

    SQLite does not create intermediate directories, and relative paths in
    ``LANGFLOW_DATABASE_URL`` are resolved by SQLAlchemy against the current
    working directory at connect time. When the resolved parent directory is
    missing the raw ``sqlite3.OperationalError`` ("unable to open database file")
    is opaque, so surface where the database open was actually attempted and how
    a relative path was resolved. No-op for non-SQLite and in-memory URLs.

    Note: this only improves diagnostics; it does not change which URLs are
    accepted nor create any directories.
    """
    db_path = get_sqlite_database_file_path(database_url)
    if db_path is None:
        return

    resolved = db_path.resolve()
    logger.debug(f"Using SQLite database at {resolved}")

    parent = resolved.parent
    if parent.exists():
        return

    msg = (
        f"Cannot open the SQLite database at '{resolved}': the parent directory "
        f"'{parent}' does not exist, and SQLite does not create intermediate "
        f"directories. "
    )
    if db_path.is_absolute():
        msg += "Create the directory before starting the server, or point LANGFLOW_DATABASE_URL at an existing path."
    else:
        msg += (
            f"The relative path '{db_path}' from LANGFLOW_DATABASE_URL was resolved against the current working "
            f"directory ('{Path.cwd()}'). Set LANGFLOW_DATABASE_URL to an absolute path "
            f"(e.g. 'sqlite:///{resolved}'), or create the directory before starting the server."
        )
    raise ValueError(msg)


def check_schema_at_head_sync(
    database_url: str,
    *,
    script_location: Path,
    version_table: str,
) -> tuple[bool, str | None, str | None]:
    """Synchronously check whether ``database_url``'s schema is at migration head.

    Fork-safe pre-flight for ``lfx serve``: opens a short-lived sync connection,
    reads the current revision from ``version_table``, and compares it to the
    stream's head. Returns ``(at_head, current, head)``. A missing version table
    reads as ``current=None`` (never migrated). Never creates the async engine,
    so it is safe to call in the parent before workers fork.
    """
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(script_location))
    head = script.get_current_head()

    engine = sa.create_engine(_normalize_sync_postgres_url(database_url))
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"version_table": version_table})
            current = ctx.get_current_revision()
    finally:
        engine.dispose()

    return current == head, current, head


class SchemaNotAtHeadError(RuntimeError):
    """Raised when a boot-time schema check finds pending migrations.

    lfx does not migrate implicitly on ``serve`` (explicit-only policy): the
    operator runs ``lfx db upgrade`` (or an init container) first. This error
    tells them exactly that.
    """


class DatabaseService(Service):
    """Tier 1 infrastructure service: pooled async engine + alembic runner.

    The migration *stream* (which alembic tree, which version table) is
    overridable so langflow's subclass can drive its own lineage while sharing
    every line of engine/session/migration mechanism. Defaults target lfx's own
    stream so a bare ``lfx`` install is self-sufficient.
    """

    name = "database_service"

    # Tier 1 infrastructure port. A real engine persists across restarts; SHARED
    # (cross-process) is only true for Postgres, so the static class-level
    # guarantee is the intersection: {PERSISTENT}. (A backend that wants to
    # advertise SHARED can override per deployment.)
    tier: ClassVar[Tier] = Tier.INFRASTRUCTURE
    capabilities: ClassVar[frozenset[Capability]] = frozenset({Capability.PERSISTENT})

    # --- Migration-stream identity (overridable by subclasses) -------------
    # The alembic version table this service's stream stamps. lfx uses a
    # distinct name from langflow's default ``alembic_version`` so the two
    # lineages never collide if they ever meet in the same database.
    alembic_version_table: ClassVar[str] = "lfx_alembic_version"
    # Tables this service is responsible for provisioning, used only for the
    # post-``create_db_and_tables`` sanity check. langflow overrides with its
    # fuller set. Migrations remain the source of truth in production.
    expected_tables: ClassVar[tuple[str, ...]] = ("message", "transaction", "vertex_build")

    def session_scope(self):
        """Async write session scope over this service (auto-commit/rollback).

        Part of the Tier 1 database port (Option B): Tier 2 services call this on
        their injected ``database_service``. Delegates to the shared helper so
        semantics match the module-level ``lfx.services.deps.session_scope``.
        """
        from lfx.services.database.session import session_scope_for

        return session_scope_for(self)

    def session_scope_readonly(self):
        """Read-only session scope over this service (no commit/rollback)."""
        from lfx.services.database.session import session_scope_readonly_for

        return session_scope_readonly_for(self)

    def __init__(self, settings_service: SettingsService):
        self._logged_pragma = False
        self.settings_service = settings_service
        if settings_service.settings.database_url is None:
            msg = "No database URL provided"
            raise ValueError(msg)
        self.database_url: str = settings_service.settings.database_url

        configure_windows_postgres_event_loop(source="database_service")

        self._sanitize_database_url()

        # Migration-stream location: subclasses override to point at their own
        # alembic tree. Defaults to lfx's own migrations package.
        self.script_location = self._resolve_script_location()
        self.alembic_cfg_path = self.script_location / "alembic.ini"

        # register the event listener for sqlite as part of this class.
        # Using decorator will make the method not able to use self
        event.listen(Engine, "connect", self.on_connection)
        if self.settings_service.settings.database_connection_retry:
            self.engine = self._create_engine_with_retry()
        else:
            self.engine = self._create_engine()

        # Create async session maker for efficient session creation
        # This is the recommended SQLAlchemy 2.0+ pattern
        # IMPORTANT: Must use SQLModel's AsyncSession (not SQLAlchemy's) for exec() method
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=SQLModelAsyncSession,  # SQLModel's AsyncSession with exec() support
            expire_on_commit=False,
        )

        # Check if Alembic should log to stdout or a file.
        # If file, check if the provided path is absolute, cross-platform.
        alembic_log_file = self.settings_service.settings.alembic_log_file
        self.alembic_log_to_stdout = self.settings_service.settings.alembic_log_to_stdout
        if self.alembic_log_to_stdout:
            self.alembic_log_path = None
        elif Path(alembic_log_file).is_absolute():
            self.alembic_log_path = Path(alembic_log_file)
        else:
            # Resolve relative log paths against the writable runtime config
            # directory, not the installed package directory. The package dir is
            # read-only in hardened deployments (non-root containers, read-only
            # root filesystems, Kubernetes), where writing into it raises OSError
            # and crashes startup. config_dir is always writable (it defaults to
            # platformdirs' user cache dir and is created on startup).
            config_dir = getattr(self.settings_service.settings, "config_dir", None)
            base_dir = Path(config_dir) if config_dir else self.script_location.parent
            self.alembic_log_path = base_dir / alembic_log_file

    @classmethod
    def default_script_location(cls) -> Path:
        """Alembic ``script_location`` for lfx's stream, resolvable without an instance.

        Ships inside the package so a wheel-only install can run ``lfx db upgrade``.
        Exposed as a classmethod so the CLI can build a Config without constructing
        the service (and thus without opening an engine).
        """
        return Path(__file__).parent / "migrations"

    def _resolve_script_location(self) -> Path:
        """Return the alembic ``script_location`` for this service's stream.

        Subclasses override to drive a different lineage (langflow points this at
        its own alembic tree).
        """
        return self.default_script_location()

    @classmethod
    def make_cli_config(cls, settings_service: SettingsService, *, stdout=None) -> Config:
        """Build an alembic ``Config`` for this stream without opening an engine.

        The ``lfx db`` commands drive alembic directly (``command.upgrade`` etc.);
        the env module creates its own short-lived engine, so we deliberately do
        not instantiate the service here.
        """
        url = settings_service.settings.database_url
        if url is None:
            msg = "No database URL provided"
            raise ValueError(msg)
        cfg = Config(stdout=stdout if stdout is not None else sys.stdout)
        cfg.set_main_option("script_location", str(cls.default_script_location()))
        cfg.set_main_option("sqlalchemy.url", to_async_driver_url(url).replace("%", "%%"))
        return cfg

    async def initialize_alembic_log_file(self):
        log_path = self.alembic_log_path
        if self.alembic_log_to_stdout or log_path is None:
            return

        # Ensure the directory and file for the alembic log file exists. The
        # migration log is diagnostic-only, so a read-only filesystem (hardened
        # containers / Kubernetes) must never abort startup: warn and move on.
        def _touch() -> None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch(exist_ok=True)

        try:
            await asyncio.to_thread(_touch)
        except OSError as exc:
            await logger.awarning(
                f"Could not initialize the Alembic migration log at '{log_path}' ({exc}). "
                "Migration output falls back to stdout. Set LANGFLOW_ALEMBIC_LOG_FILE to a writable path "
                "or LANGFLOW_ALEMBIC_LOG_TO_STDOUT=true to silence this warning."
            )

    def reload_engine(self) -> None:
        self._sanitize_database_url()
        if self.settings_service.settings.database_connection_retry:
            self.engine = self._create_engine_with_retry()
        else:
            self.engine = self._create_engine()

        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=SQLModelAsyncSession,
            expire_on_commit=False,
        )

    def _sanitize_database_url(self):
        """Normalise the database URL to an async driver in place."""
        driver = self.database_url.split("://", maxsplit=1)[0]
        if driver == "postgres":
            logger.warning(
                "The postgres dialect in the database URL is deprecated. "
                "Use postgresql instead. "
                "To avoid this warning, update the database URL."
            )
        self.database_url = to_async_driver_url(self.database_url)

    def _build_connection_kwargs(self):
        """Build connection kwargs by merging deprecated settings with db_connection_settings.

        Returns:
            dict: Connection kwargs with deprecated settings overriding db_connection_settings
        """
        settings = self.settings_service.settings
        # Start with db_connection_settings as base
        connection_kwargs = settings.db_connection_settings.copy()

        # Override individual settings if explicitly set
        if "pool_size" in settings.model_fields_set:
            logger.warning("pool_size is deprecated. Use db_connection_settings['pool_size'] instead.")
            connection_kwargs["pool_size"] = settings.pool_size
        if "max_overflow" in settings.model_fields_set:
            logger.warning("max_overflow is deprecated. Use db_connection_settings['max_overflow'] instead.")
            connection_kwargs["max_overflow"] = settings.max_overflow

        return connection_kwargs

    def _create_engine(self) -> AsyncEngine:
        # Get connection settings from config, with defaults if not specified
        # if the user specifies an empty dict, we allow it.
        kwargs = self._build_connection_kwargs()

        poolclass_key = kwargs.get("poolclass")
        if poolclass_key is not None:
            pool_class = getattr(sa.pool, poolclass_key, None)
            if pool_class and issubclass(pool_class, sa.pool.Pool):
                logger.debug(f"Using poolclass: {poolclass_key}.")
                kwargs["poolclass"] = pool_class
            else:
                logger.error(f"Invalid poolclass '{poolclass_key}' specified. Using default pool class.")
                kwargs.pop("poolclass", None)

        return create_async_engine(
            self.database_url,
            connect_args=self._get_connect_args(),
            **kwargs,
        )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(10))
    def _create_engine_with_retry(self) -> AsyncEngine:
        """Create the engine for the database with retry logic."""
        return self._create_engine()

    def _get_connect_args(self):
        settings = self.settings_service.settings

        if settings.db_driver_connection_settings is not None:
            return settings.db_driver_connection_settings

        if settings.database_url and settings.database_url.startswith("sqlite"):
            return {
                "check_same_thread": False,
                "timeout": settings.db_connect_timeout,
            }
        # For PostgreSQL, set the timezone to UTC
        if settings.database_url and settings.database_url.startswith(("postgresql", "postgres")):
            return {"options": "-c timezone=utc"}
        return {}

    def on_connection(self, dbapi_connection, _connection_record) -> None:
        if isinstance(dbapi_connection, sqlite3.Connection | dialect_sqlite.aiosqlite.AsyncAdapt_aiosqlite_connection):
            pragmas: dict = self.settings_service.settings.sqlite_pragmas or {}
            pragmas_list = []
            for key, val in pragmas.items():
                pragmas_list.append(f"PRAGMA {key} = {val}")
            if not self._logged_pragma:
                logger.debug(f"sqlite connection, setting pragmas: {pragmas_list}")
                self._logged_pragma = True
            if pragmas_list:
                cursor = dbapi_connection.cursor()
                try:
                    for pragma in pragmas_list:
                        try:
                            cursor.execute(pragma)
                        except OperationalError:
                            logger.exception(f"Failed to set PRAGMA {pragma}")
                        except GeneratorExit:
                            logger.error(f"Failed to set PRAGMA {pragma}")
                finally:
                    cursor.close()

    @asynccontextmanager
    async def _with_session(self):
        """Internal method to create a session. DO NOT USE DIRECTLY.

        Use session_scope() for write operations or session_scope_readonly() for read operations.
        This method does not handle commits - it only provides a raw session.
        """
        if self.settings_service.settings.use_noop_database:
            from lfx.services.session import NoopSession

            async with NoopSession() as session:
                yield session
        else:
            # Use async_session_maker - the recommended SQLAlchemy 2.0+ pattern
            # Provides efficient session creation and proper connection pooling
            async with self.async_session_maker() as session:
                yield session

    async def ensure_postgresql_version(self) -> None:
        """If the database is PostgreSQL, ensure it is version 15 or higher.

        The schema uses UNIQUE NULLS DISTINCT, which is only supported in PostgreSQL 15+.
        Logs the message and raises UnsupportedPostgreSQLVersionError if the version is too old.
        """
        if not self.database_url.startswith(("postgresql", "postgres")):
            return
        if self.settings_service.settings.use_noop_database:
            return
        async with session_scope() as session:
            result = await session.execute(_PG_VERSION_QUERY)
            version_num_str, version_str = result.fetchone()
        # Raise AFTER session_scope exits so session_scope doesn't log a
        # noisy "An error occurred during the session scope." traceback.
        _check_version_row(version_num_str, version_str)

    # --- Alembic migration runner ------------------------------------------

    def _make_alembic_config(self, buffer) -> Config:
        alembic_cfg = Config(stdout=buffer)
        alembic_cfg.set_main_option("script_location", str(self.script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", self.database_url.replace("%", "%%"))
        return alembic_cfg

    def init_alembic(self, alembic_cfg) -> None:
        logger.info("Initializing alembic")
        command.ensure_version(alembic_cfg)
        command.upgrade(alembic_cfg, "head")

    def _open_alembic_log_buffer(self):
        """Open the Alembic migration log for writing, falling back to stdout.

        The migration log is diagnostic-only output. If the target path cannot
        be written -- e.g. the installed package directory or the root
        filesystem is read-only, as in hardened container/Kubernetes deployments
        (non-root user or read-only root filesystem) -- migration must not abort.
        Fall back to stdout rather than letting OSError propagate. Returns a
        context manager yielding the buffer Alembic writes its output to.
        """
        log_path = self.alembic_log_path
        if self.alembic_log_to_stdout or log_path is None:
            return nullcontext(sys.stdout)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            return log_path.open("w", encoding="utf-8")
        except OSError as exc:
            logger.warning(
                f"Could not open the Alembic migration log at '{log_path}' ({exc}). "
                "Falling back to stdout. Set LANGFLOW_ALEMBIC_LOG_FILE to a writable path "
                "or LANGFLOW_ALEMBIC_LOG_TO_STDOUT=true to silence this warning."
            )
            return nullcontext(sys.stdout)

    def _run_migrations(self, should_initialize_alembic, fix) -> None:
        # The advisory lock serialises concurrent migration runs across workers
        # so they do not race on CREATE TYPE / CREATE TABLE against a fresh PG.
        buffer_context = self._open_alembic_log_buffer()
        with _postgres_migration_lock(self.database_url), buffer_context as buffer:
            alembic_cfg = self._make_alembic_config(buffer)

            if should_initialize_alembic:
                try:
                    self.init_alembic(alembic_cfg)
                except Exception as exc:
                    msg = f"Error initializing alembic: {exc}"
                    logger.exception(msg)
                    raise RuntimeError(msg) from exc
            else:
                logger.debug("Alembic initialized")

            try:
                buffer.write(f"{datetime.now(tz=timezone.utc).astimezone().isoformat()}: Checking migrations\n")
                command.check(alembic_cfg)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Error checking migrations: {exc}")
                if isinstance(exc, util.exc.CommandError | util.exc.AutogenerateDiffsDetected):
                    command.upgrade(alembic_cfg, "head")
                    time.sleep(3)

            try:
                buffer.write(f"{datetime.now(tz=timezone.utc).astimezone()}: Checking migrations\n")
                command.check(alembic_cfg)
            except util.exc.AutogenerateDiffsDetected as exc:
                logger.exception("Error checking migrations")
                if not fix:
                    msg = f"There's a mismatch between the models and the database.\n{exc}"
                    raise RuntimeError(msg) from exc

            if fix:
                self.try_downgrade_upgrade_until_success(alembic_cfg)

    async def run_migrations(self, *, fix=False) -> None:
        should_initialize_alembic = False
        async with session_scope() as session:
            # If the version table does not exist it throws an error, so we
            # catch it and initialize this stream's alembic bookkeeping.
            try:
                await session.exec(text(f"SELECT * FROM {self.alembic_version_table}"))  # noqa: S608
            except Exception:  # noqa: BLE001
                await logger.adebug("Alembic not initialized")
                should_initialize_alembic = True
        await asyncio.to_thread(self._run_migrations, should_initialize_alembic, fix)

    @staticmethod
    def try_downgrade_upgrade_until_success(alembic_cfg, retries=5) -> None:
        # Try -1 then head, if it fails, try -2 then head, etc.
        # until we reach the number of retries
        for i in range(1, retries + 1):
            try:
                command.check(alembic_cfg)
                break
            except util.exc.AutogenerateDiffsDetected:
                # downgrade to base and upgrade again
                logger.warning("AutogenerateDiffsDetected")
                command.downgrade(alembic_cfg, f"-{i}")
                # wait for the database to be ready
                time.sleep(3)
                command.upgrade(alembic_cfg, "head")

    async def schema_is_at_head(self) -> bool:
        """Return True when this stream's schema is fully migrated.

        Used by the explicit-migration boot policy: ``lfx serve`` verifies the
        schema is at head and refuses to start otherwise (rather than migrating
        implicitly). Returns False when the version table is missing or when
        alembic reports pending autogenerate diffs.
        """
        # First, cheap existence check: no version table means "never migrated".
        async with session_scope() as session:
            try:
                await session.exec(text(f"SELECT * FROM {self.alembic_version_table}"))  # noqa: S608
            except Exception:  # noqa: BLE001
                return False
        return await asyncio.to_thread(self._check_at_head)

    def _check_at_head(self) -> bool:
        with nullcontext(sys.stdout) as buffer:
            alembic_cfg = self._make_alembic_config(buffer)
            try:
                command.check(alembic_cfg)
            except util.exc.AutogenerateDiffsDetected:
                return False
            except util.exc.CommandError:
                # e.g. target database is not up to date
                return False
            return True

    async def ensure_schema_at_head_or_raise(self) -> None:
        """Raise :class:`SchemaNotAtHeadError` unless the schema is at head.

        The explicit-only migration policy: bare ``lfx serve`` does not migrate
        implicitly. Operators run ``lfx db upgrade`` (or an init container).
        """
        if self.settings_service.settings.use_noop_database:
            return
        if await self.schema_is_at_head():
            return
        msg = (
            "Database schema is not at head (pending migrations). lfx does not migrate "
            "automatically on serve. Run 'lfx db upgrade' (or an init container / job) "
            "against LANGFLOW_DATABASE_URL before starting the server."
        )
        raise SchemaNotAtHeadError(msg)

    # --- create_all fallback (dev/test convenience; migrations own prod) ----

    def _create_db_and_tables(self, connection) -> None:
        from sqlalchemy import inspect

        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        current_tables = list(self.expected_tables)

        if table_names and all(table in table_names for table in current_tables):
            logger.debug("Database and tables already exist")
            return

        logger.debug("Creating database and tables")

        for table in SQLModel.metadata.sorted_tables:
            try:
                table.create(connection, checkfirst=True)
            except OperationalError as oe:
                logger.warning(f"Table {table} already exists, skipping. Exception: {oe}")
            except Exception as exc:
                msg = f"Error creating table {table}"
                logger.exception(msg)
                raise RuntimeError(msg) from exc

        # Now check if the required tables exist, if not, something went wrong.
        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        for table in current_tables:
            if table not in table_names:
                logger.error("Something went wrong creating the database and tables.")
                logger.error("Please check your database settings.")
                msg = "Something went wrong creating the database and tables."
                raise RuntimeError(msg)

        logger.debug("Database and tables created successfully")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(10))
    async def create_db_and_tables_with_retry(self) -> None:
        await self.create_db_and_tables()

    async def create_db_and_tables(self) -> None:
        if not self.database_url.startswith(("postgresql", "postgres")):
            # SQLite / non-PG: original async path; advisory lock does not apply.
            async with self.engine.begin() as conn:
                await conn.run_sync(self._create_db_and_tables)
            return

        # Postgres: serialise CREATE TYPE / CREATE TABLE across workers under
        # the same advisory lock that protects run_migrations.
        await asyncio.to_thread(self._create_db_and_tables_with_lock)

    def _create_db_and_tables_with_lock(self) -> None:
        """Postgres path: hold the migration advisory lock for the DDL.

        Opens its own sync engine so the DDL runs on the same driver the lock
        uses; the application's async engine is unaffected.
        """
        with _postgres_migration_lock(self.database_url):
            sync_engine = sa.create_engine(_normalize_sync_postgres_url(self.database_url))
            try:
                with sync_engine.begin() as conn:
                    self._create_db_and_tables(conn)
            finally:
                sync_engine.dispose()

    async def teardown(self) -> None:
        await logger.adebug("Tearing down database")
        await self.engine.dispose()
