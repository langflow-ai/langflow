"""Classify database revisions before running any schema changes."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import parse_qs, unquote, urlsplit

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import RevisionError
from alembic.util.exc import CommandError
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncEngine

LEGACY_REVISIONS = frozenset({"826cfcc8c8a0", "90c977dcf0f1", "d49cbced8696"})
LEGACY_BRANCH_POINT = "e1705947c729"  # pragma: allowlist secret
RESTORE_GUIDE = "https://docs.langflow.org/get-started-installation#restore-before-rolling-back"


class DatabaseRevisionError(RuntimeError):
    """The installed migrations cannot safely handle the database revision."""


@dataclass(frozen=True)
class RevisionState:
    kind: Literal["known", "legacy", "unknown"]
    revisions: frozenset[str]
    message: str
    upgrade_from: str | None = None

    def require_supported(self) -> None:
        if self.kind == "unknown":
            raise DatabaseRevisionError(self.message)


def script_directory(location: Path | None = None) -> ScriptDirectory:
    """Read the migration graph shipped with this Langflow installation."""
    config = Config()
    config.set_main_option("script_location", str(location or Path(__file__).parents[2] / "alembic"))
    return ScriptDirectory.from_config(config)


def classify_revisions(revisions: Iterable[str], script: ScriptDirectory | None = None) -> RevisionState:
    """Recognize normal revisions and the supported 1.10.3 side branch."""
    revisions = frozenset(revisions)
    script = script or script_directory()
    found = ", ".join(sorted(revisions)) or "no recorded revision"
    unknown = (
        f"Refusing to start on database revision {found}. This release does not recognize the revision "
        "or the recorded revisions overlap. The database may belong to a newer Langflow release. "
        f"Use that release or restore a matching backup before rolling back. See {RESTORE_GUIDE}"
    )
    if not revisions:
        return RevisionState("known", revisions, "database has no recorded revision")
    try:
        if (
            len(revisions) == 1
            and revisions <= LEGACY_REVISIONS
            and script.get_revision(LEGACY_BRANCH_POINT) is not None
        ):
            return RevisionState(
                "legacy",
                revisions,
                f"database uses a supported Langflow 1.10.3 side branch ({found}); "
                f"upgrade from its branch point {LEGACY_BRANCH_POINT}",
                LEGACY_BRANCH_POINT,
            )
        known = {revision.revision for revision in script.walk_revisions()}
        if not revisions <= known:
            return RevisionState("unknown", revisions, unknown)
        script.get_revisions(tuple(revisions))
        # Alembic rejects ancestor and descendant revisions recorded together.
        tuple(script.iterate_revisions("heads", tuple(revisions)))
    except (CommandError, RevisionError):
        return RevisionState("unknown", revisions, unknown)
    return RevisionState("known", revisions, f"database at revision {found}")


def _sqlite_revisions(path: Path) -> set[str]:
    # Bypass application connection hooks which set persistent SQLite pragmas.
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        version_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        if not version_table:
            return set()
        return {row[0] for row in connection.execute("SELECT version_num FROM alembic_version")}
    finally:
        connection.close()


@dataclass(frozen=True)
class SQLiteDatabaseTarget:
    database: str
    in_memory: bool


def sqlite_database_target(
    database_url: str | URL, connect_args: Mapping[str, object] | None = None
) -> SQLiteDatabaseTarget | None:
    """Resolve SQLite's filename using the effective DBAPI connection options."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    arguments, options = url.get_dialect()().create_connect_args(url)
    options.update(connect_args or {})
    database = arguments[0]
    # Only file: names with effective URI mode enabled interpret query options.
    uri = urlsplit(database) if options.get("uri", False) and database.startswith("file:") else None
    if uri is not None:
        database = unquote(uri.path)
    in_memory = database == ":memory:" or (uri is not None and parse_qs(uri.query).get("mode") == ["memory"])
    return SQLiteDatabaseTarget(database=database, in_memory=in_memory)


async def read_revisions_before_startup(
    engine: AsyncEngine, connect_args: Mapping[str, object] | None = None
) -> set[str]:
    """Read existing state without creating tables or changing SQLite pragmas."""
    target = sqlite_database_target(engine.url, connect_args)
    if target is not None and target.database and not target.in_memory:
        path = Path(target.database)
        if not path.exists():
            return set()
        return await asyncio.to_thread(_sqlite_revisions, path)
    async with engine.connect() as connection:
        if not await connection.run_sync(lambda sync: inspect(sync).has_table("alembic_version")):
            return set()
        return set((await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars())
