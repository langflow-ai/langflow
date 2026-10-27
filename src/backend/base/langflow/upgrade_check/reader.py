"""Read a source database for the upgrade check, without changing it.

The upgrade check runs the target release's code against the database of the release
it upgrades from, before the upgrade. That database belongs to an older release, so
this reads it with plain SQL instead of this release's models: ``select(Flow)`` would
ask for columns that 1.12.6 and older do not have. Every column read here exists in
every release from 1.10 on, and the tables that came later are checked before they are
read.

Read-only is enforced at the connection, not by care: SQLite opens in ``mode=ro`` and
keeps its journal mode, and Postgres reads inside a read-only transaction. Nothing here
starts Langflow's services, builds its settings, or touches a secret key.

Langflow keeps SQLite in WAL mode, and SQLite reads a WAL database through a ``-shm``
index next to the file, creating it (and an empty ``-wal``) when they are missing, even
in ``mode=ro``. Those side files hold no data and the database file stays byte for byte
the same. A folder SQLite cannot write to stops the read, and the error says what to do;
``immutable=1`` would avoid the side files but can read inconsistently while a server
writes, so it is never used.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:
    from collections.abc import Iterator

# The Postgres drivers Langflow ships do not include asyncpg, and this reader is synchronous.
_SYNC_POSTGRES_DRIVER = "postgresql+psycopg"

_READ_ONLY_FOLDER = (
    "SQLite could not read the database because its folder is not writable: a database in WAL mode "
    "needs its -shm file next to it, even to read. Mount the folder writable for the check, or copy the "
    "database into a writable folder while the server is stopped and point the check at the copy."
)


class SourceDatabaseError(RuntimeError):
    """The source database cannot be read as it is; the message says what to change."""


@dataclass(frozen=True)
class SourceUser:
    id: str
    username: str


@dataclass(frozen=True)
class SourceProject:
    id: str
    name: str


@dataclass(frozen=True)
class SourceFlow:
    """A flow or a saved component (``is_component``) as the source stored it."""

    id: str
    name: str
    data: dict | None
    user_id: str | None
    folder_id: str | None
    is_component: bool
    updated_at: str | None
    # Set when ``data`` could not be read, so one bad row does not stop the whole check.
    data_error: str | None = None


@dataclass(frozen=True)
class SourceFlowVersion:
    """A saved flow version that still runs: a trigger pins it, or a deployment has it attached."""

    id: str
    flow_id: str
    version_number: int
    data: dict | None
    user_id: str | None
    created_at: str | None
    pinned_by_triggers: tuple[str, ...]
    attached_to_deployments: tuple[str, ...]
    data_error: str | None = None


@dataclass
class SourceDatabase:
    dialect: str
    alembic_revisions: list[str]
    users: list[SourceUser] = field(default_factory=list)
    projects: list[SourceProject] = field(default_factory=list)
    flows: list[SourceFlow] = field(default_factory=list)
    flow_versions: list[SourceFlowVersion] = field(default_factory=list)
    # Which of the tables that later releases added this source has.
    has_flow_versions: bool = False
    has_triggers: bool = False
    has_deployments: bool = False


def read_source(database_url: str) -> SourceDatabase:
    """Read everything the upgrade check needs from the database at ``database_url``."""
    with read_only_connection(database_url) as connection:
        return read_connection(connection)


@contextmanager
def read_only_connection(database_url: str) -> Iterator[sa.Connection]:
    """Yield a connection that cannot write to the database at ``database_url``.

    The transaction is rolled back when the block ends, so even a statement the
    database accepted would leave nothing behind.
    """
    url = sa.make_url(database_url)
    backend = url.get_backend_name()
    if backend == "sqlite":
        engine = _sqlite_engine(url)
    elif backend in {"postgresql", "postgres"}:
        engine = sa.create_engine(url.set(drivername=_sync_postgres_driver(url)), poolclass=NullPool)
    else:
        msg = f"the upgrade check reads SQLite and PostgreSQL databases, not {backend}"
        raise ValueError(msg)
    try:
        with engine.connect() as connection:
            if backend == "sqlite":
                _check_sqlite_readable(connection)
            else:
                # Must be the transaction's first statement; Postgres then refuses every write in it.
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            try:
                yield connection
            finally:
                connection.rollback()
    finally:
        engine.dispose()


def _sqlite_engine(url: sa.URL) -> sa.Engine:
    if not url.database or url.database == ":memory:":
        msg = "the SQLite database URL must name a file"
        raise ValueError(msg)
    path = Path(url.database).expanduser().resolve()
    if not path.is_file():
        msg = f"no SQLite database at {path}"
        raise FileNotFoundError(msg)
    # A URI keeps the path exact (as_uri escapes it) and opens the file read-only. The journal
    # mode is left alone: switching to WAL, as Langflow's own engine does, would write the file.
    uri = f"{path.as_uri()}?mode=ro"
    return sa.create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True), poolclass=NullPool)


def _check_sqlite_readable(connection: sa.Connection) -> None:
    """Read the schema once, so a folder SQLite cannot write to fails here with a clear message."""
    try:
        connection.exec_driver_sql("SELECT count(*) FROM sqlite_master").scalar()
    except sa.exc.OperationalError as exc:
        # SQLITE_READONLY_DIRECTORY on Python 3.11+; older Pythons only carry the message.
        name = getattr(exc.orig, "sqlite_errorname", None)
        if name == "SQLITE_READONLY_DIRECTORY" or (name is None and "readonly database" in str(exc.orig)):
            raise SourceDatabaseError(_READ_ONLY_FOLDER) from exc
        raise


def _sync_postgres_driver(url: sa.URL) -> str:
    """Keep a sync driver the user named; otherwise use psycopg, the driver Langflow uses for Postgres."""
    if url.drivername in {"postgresql+psycopg", "postgresql+psycopg2"}:
        return url.drivername
    return _SYNC_POSTGRES_DRIVER


def read_connection(connection: sa.Connection) -> SourceDatabase:
    """Read the source through ``connection``, which the caller made read-only."""
    tables = set(sa.inspect(connection).get_table_names())
    source = SourceDatabase(
        dialect=connection.dialect.name,
        alembic_revisions=_alembic_revisions(connection, tables),
        has_flow_versions="flow_version" in tables,
        has_triggers="trigger" in tables,
        has_deployments={"deployment", "flow_version_deployment_attachment"} <= tables,
    )
    source.users = [SourceUser(_uuid(row.id), row.username) for row in _select(connection, "user", "id", "username")]
    source.projects = [SourceProject(_uuid(row.id), row.name) for row in _select(connection, "folder", "id", "name")]
    # ponytail: every flow's data is held in memory at once; stream rows if large sources need it.
    source.flows = [
        SourceFlow(
            id=_uuid(row.id),
            name=row.name,
            user_id=_uuid(row.user_id),
            folder_id=_uuid(row.folder_id),
            is_component=bool(row.is_component),
            updated_at=_timestamp(row.updated_at),
            **_flow_data(row.data),
        )
        for row in _select(
            connection, "flow", "id", "name", "data", "user_id", "folder_id", "is_component", "updated_at"
        )
    ]
    if source.has_flow_versions:
        source.flow_versions = _running_flow_versions(connection, source)
    return source


def _running_flow_versions(connection: sa.Connection, source: SourceDatabase) -> list[SourceFlowVersion]:
    """Read the saved versions that still run: pinned by a trigger or attached to a deployment."""
    triggers: dict[Any, list[str]] = {}
    if source.has_triggers and "flow_version_id" in _columns(connection, "trigger"):
        trigger = sa.table("trigger", sa.column("id"), sa.column("flow_version_id"))
        pins = sa.select(trigger.c.id, trigger.c.flow_version_id).where(trigger.c.flow_version_id.is_not(None))
        for row in connection.execute(pins):
            triggers.setdefault(row.flow_version_id, []).append(_uuid(row.id))
    deployments: dict[Any, list[str]] = {}
    if source.has_deployments:
        for row in _select(connection, "flow_version_deployment_attachment", "flow_version_id", "deployment_id"):
            deployments.setdefault(row.flow_version_id, []).append(_uuid(row.deployment_id))
    running = triggers.keys() | deployments.keys()
    if not running:
        return []
    version = sa.table(
        "flow_version",
        *(sa.column(name) for name in ("id", "flow_id", "version_number", "data", "user_id", "created_at")),
    )
    rows = connection.execute(sa.select(version).where(version.c.id.in_(list(running))))
    return [
        SourceFlowVersion(
            id=_uuid(row.id),
            flow_id=_uuid(row.flow_id),
            version_number=row.version_number,
            user_id=_uuid(row.user_id),
            created_at=_timestamp(row.created_at),
            pinned_by_triggers=tuple(sorted(triggers.get(row.id, []))),
            attached_to_deployments=tuple(sorted(deployments.get(row.id, []))),
            **_flow_data(row.data),
        )
        for row in rows
    ]


def _alembic_revisions(connection: sa.Connection, tables: set[str]) -> list[str]:
    if "alembic_version" not in tables:
        return []
    return sorted(row.version_num for row in _select(connection, "alembic_version", "version_num"))


def _select(connection: sa.Connection, table_name: str, *column_names: str):
    # sa.table quotes names a dialect reserves, such as Postgres's "user".
    table = sa.table(table_name, *(sa.column(name) for name in column_names))
    return connection.execute(sa.select(table))


def _columns(connection: sa.Connection, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(connection).get_columns(table_name)}


def _uuid(value: Any) -> str | None:
    """SQLite stores ids as 32 hex characters and Postgres as uuid; report both one way."""
    return None if value is None else str(UUID(str(value)))


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _flow_data(value: Any) -> dict[str, Any]:
    """Return ``data`` and ``data_error`` for a stored flow: JSON text on SQLite, already parsed on Postgres."""
    if value is None or isinstance(value, dict):
        return {"data": value, "data_error": None}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        return {"data": None, "data_error": f"flow data is not JSON: {exc}"}
    if not isinstance(parsed, dict):
        return {"data": None, "data_error": f"flow data is a JSON {type(parsed).__name__}, not an object"}
    return {"data": parsed, "data_error": None}
