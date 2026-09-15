"""Copy a Langflow SQLite database into Postgres.

No dump tool crosses the two engines: ``pg_dump`` cannot read SQLite, and
SQLite's ``.dump`` emits DDL Postgres rejects. So this builds the Postgres schema
with Langflow's own alembic migrations and then moves rows, converting each
value to the type the Postgres column declares.

It refuses rather than guesses. Nothing is written until the whole source has
been checked, the copy runs in one transaction, and every table's row count has
to match before it commits.
"""

from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects.postgresql import insert

if TYPE_CHECKING:
    from collections.abc import Iterator

# Postgres caps bind parameters per statement at 65535.
_MAX_PARAMS_PER_STATEMENT = 60_000
_VERSION_TABLE = "alembic_version"


@dataclass
class TableCopy:
    name: str
    source_rows: int
    target_rows: int


@dataclass
class ConversionReport:
    revision: str | None = None
    tables: list[TableCopy] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def convert_sqlite_to_postgres(source_url: str, target_url: str, *, batch_size: int = 1000) -> ConversionReport:
    """Copy every row of a SQLite Langflow database into a Postgres database.

    The target may be empty or a previous run of this conversion. Returns a
    report; ``report.ok`` is False and nothing is committed when anything was
    refused or failed.
    """
    report = ConversionReport()
    source = sa.create_engine(_sync_sqlite_url(source_url))
    target_sync_url = _sync_postgres_url(target_url)
    try:
        head = _script_head()
        source_revision = _revision(source)
        report.revision = source_revision
        if source_revision != head:
            report.problems.append(
                f"source database is at revision {source_revision}, this Langflow expects {head}; "
                "start this Langflow version against the SQLite database once so it migrates, then convert"
            )
            return report

        upgrade_to_head(target_url)
        target = sa.create_engine(target_sync_url)
        try:
            _convert(source, target, report, batch_size=batch_size)
        finally:
            target.dispose()
    finally:
        source.dispose()
    return report


def upgrade_to_head(database_url: str) -> None:
    """Build or migrate a database's schema with Langflow's own alembic migrations."""
    config = Config(stdout=io.StringIO())
    config.set_main_option("script_location", str(_script_location()))
    config.set_main_option("sqlalchemy.url", _async_url(database_url).replace("%", "%%"))
    command.upgrade(config, "head")


def copy_order(metadata: sa.MetaData) -> list[sa.Table]:
    """Tables in the order rows can be inserted: every table after the tables it references."""
    tables = [table for table in metadata.sorted_tables if table.name != _VERSION_TABLE]
    names = [table.name for table in tables]
    # sso_settings.enforce_sso and sso_config.enforce_sso are kept in sync by a
    # trigger in both directions, so the singleton goes after the rows it mirrors.
    if "sso_config" in names and "sso_settings" in names:
        settings = tables.pop(names.index("sso_settings"))
        tables.insert([table.name for table in tables].index("sso_config") + 1, settings)
    return tables


def coerce_value(value: Any, column_type: sa.types.TypeEngine) -> Any:
    """Turn a raw SQLite value into what a Postgres column of ``column_type`` expects."""
    if value is None:
        return None
    if isinstance(column_type, sa.Boolean):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes"}
        return bool(value)
    if isinstance(column_type, sa.Uuid):
        # SQLite stores sa.Uuid as 32 hex characters; rows written as raw strings
        # may be dashed. uuid.UUID accepts both.
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    if isinstance(column_type, sa.JSON):
        return json.loads(value) if isinstance(value, (str, bytes)) else value
    if isinstance(column_type, sa.DateTime):
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if column_type.timezone and parsed.tzinfo is None:
            # Langflow writes UTC. SQLite drops the offset, so restore it.
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    if isinstance(column_type, sa.Date) and not isinstance(value, date):
        return date.fromisoformat(str(value))
    return value


def _convert(source: sa.Engine, target: sa.Engine, report: ConversionReport, *, batch_size: int) -> None:
    metadata = sa.MetaData()
    metadata.reflect(bind=target)
    source_tables = set(sa.inspect(source).get_table_names())
    tables = [table for table in copy_order(metadata) if table.name in source_tables]

    with source.connect() as src:
        source_columns = {table.name: _source_columns(src, table.name) for table in tables}
        report.problems.extend(_invalid_enum_values(src, tables, source_columns))
        with target.connect() as tgt:
            report.problems.extend(_foreign_users(src, tgt))
        if report.problems:
            return

        try:
            with target.begin() as tgt:
                _align_system_roles(src, tgt)
                for table in tables:
                    columns = [column for column in table.columns if column.name in source_columns[table.name]]
                    source_rows = _copy_table(src, tgt, table, columns, batch_size=batch_size)
                    target_rows = tgt.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
                    report.tables.append(TableCopy(table.name, source_rows, target_rows))
                    if target_rows != source_rows:
                        report.problems.append(
                            f"{table.name}: source has {source_rows} rows, target has {target_rows} after copy"
                        )
                if report.problems:
                    msg = "row counts differ"
                    raise _RollbackError(msg)
                _reset_sequences(tgt)
        except _RollbackError:
            pass
        except sa.exc.SQLAlchemyError as exc:
            report.problems.append(f"copy failed and was rolled back: {exc.__class__.__name__}: {exc.orig or exc}")


class _RollbackError(Exception):
    """Raised inside the copy transaction to roll it back after recording problems."""


def _source_columns(conn: sa.Connection, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table)}


def _invalid_enum_values(conn: sa.Connection, tables: list[sa.Table], source_columns: dict[str, set[str]]) -> list[str]:
    """Postgres enforces enum membership and SQLite does not, so check before writing anything.

    A bad value would otherwise fail only when its row is reached, partway through the copy.
    """
    problems = []
    for table in tables:
        for column in table.columns:
            if not isinstance(column.type, sa.Enum) or column.name not in source_columns[table.name]:
                continue
            allowed = set(column.type.enums)
            quoted = f'"{column.name}"'
            found = {row[0] for row in conn.execute(sa.text(f'SELECT DISTINCT {quoted} FROM "{table.name}"'))}  # noqa: S608
            bad = sorted(str(value) for value in found - allowed if value is not None)
            if bad:
                problems.append(
                    f"{table.name}.{column.name} holds {bad}, which {column.type.name} does not allow "
                    f"(allowed: {sorted(allowed)})"
                )
    return problems


def _foreign_users(src: sa.Connection, tgt: sa.Connection) -> list[str]:
    """Refuse to merge two instances: the target may only hold users this source also has."""
    source_ids = {coerce_value(row[0], sa.Uuid()) for row in src.execute(sa.text('SELECT id FROM "user"'))}
    target_ids = {row[0] for row in tgt.execute(sa.text('SELECT id FROM "user"'))}
    extra = target_ids - source_ids
    if not extra:
        return []
    return [
        f"target already holds {len(extra)} user(s) that are not in the source, so it belongs to another instance; "
        "convert into an empty database"
    ]


def _align_system_roles(src: sa.Connection, tgt: sa.Connection) -> None:
    """Give the target's seeded system roles the source's ids, before any other write.

    Both databases seed admin, developer and viewer with ids generated per
    install. Rewriting the target's three to match the source lets every
    assignment and custom role carry across unchanged. It has to come first:
    there is no ON UPDATE CASCADE, so once a row references a seeded role the
    rewrite fails.
    """
    for name, source_id in src.execute(sa.text("SELECT name, id FROM authz_role WHERE is_system")):
        tgt.execute(
            sa.text("UPDATE authz_role SET id = :source_id WHERE name = :name AND is_system AND id <> :source_id"),
            {"source_id": coerce_value(source_id, sa.Uuid()), "name": name},
        )


def _copy_table(
    src: sa.Connection,
    tgt: sa.Connection,
    table: sa.Table,
    columns: list[sa.Column],
    *,
    batch_size: int,
) -> int:
    names = [column.name for column in columns]
    select_sql = sa.text(
        f'SELECT {", ".join(f"{chr(34)}{name}{chr(34)}" for name in names)} FROM "{table.name}"'  # noqa: S608
    )
    rows = (
        {column.name: coerce_value(value, column.type) for column, value in zip(columns, raw, strict=True)}
        for raw in src.execute(select_sql)
    )
    if _self_parent_column(table):
        rows = iter(_parents_first(list(rows), table))

    primary_key = [column.name for column in table.primary_key.columns]
    per_batch = max(1, min(batch_size, _MAX_PARAMS_PER_STATEMENT // max(1, len(names))))
    copied = 0
    for batch in _batches(rows, per_batch):
        statement = insert(table).values(batch)
        if primary_key:
            updates = {name: statement.excluded[name] for name in names if name not in primary_key}
            statement = (
                statement.on_conflict_do_update(index_elements=primary_key, set_=updates)
                if updates
                else statement.on_conflict_do_nothing(index_elements=primary_key)
            )
        tgt.execute(statement)
        copied += len(batch)
    return copied


def _self_parent_column(table: sa.Table) -> tuple[str, str] | None:
    for foreign_key in table.foreign_keys:
        if foreign_key.column.table.name == table.name:
            return foreign_key.parent.name, foreign_key.column.name
    return None


def _parents_first(rows: list[dict[str, Any]], table: sa.Table) -> list[dict[str, Any]]:
    """Order a self-referencing table so each row comes after the row it points at."""
    parent_column, key_column = _self_parent_column(table)  # type: ignore[misc]
    placed: set[Any] = set()
    ordered: list[dict[str, Any]] = []
    pending = rows
    while pending:
        ready = [row for row in pending if row[parent_column] is None or row[parent_column] in placed]
        if not ready:
            # A cycle or a dangling parent. Insert the rest and let the database
            # report the violation rather than dropping rows silently.
            ordered.extend(pending)
            break
        ordered.extend(ready)
        placed.update(row[key_column] for row in ready)
        ready_ids = {id(row) for row in ready}
        pending = [row for row in pending if id(row) not in ready_ids]
    return ordered


def _batches(rows: Iterator[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _reset_sequences(tgt: sa.Connection) -> None:
    """Move every serial or identity sequence past the ids the copy wrote explicitly."""
    sequences = tgt.execute(
        sa.text(
            "SELECT table_name, column_name, pg_get_serial_sequence(quote_ident(table_name), column_name) "
            "FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND (column_default LIKE 'nextval(%' OR is_identity = 'YES')"
        )
    ).all()
    for table_name, column_name, sequence in sequences:
        if sequence is None:
            continue
        tgt.execute(
            sa.text(
                f'SELECT setval(:sequence, COALESCE(MAX("{column_name}"), 1), MAX("{column_name}") IS NOT NULL) '  # noqa: S608
                f'FROM "{table_name}"'
            ),
            {"sequence": sequence},
        )


def _revision(engine: sa.Engine) -> str | None:
    with engine.connect() as conn:
        if not sa.inspect(conn).has_table(_VERSION_TABLE):
            return None
        revisions = conn.execute(sa.text(f"SELECT version_num FROM {_VERSION_TABLE}")).scalars().all()  # noqa: S608
    return revisions[0] if len(revisions) == 1 else None


def _script_location() -> Path:
    import langflow

    return Path(langflow.__file__).parent / "alembic"


def _script_head() -> str | None:
    config = Config()
    config.set_main_option("script_location", str(_script_location()))
    return ScriptDirectory.from_config(config).get_current_head()


def _sync_sqlite_url(url: str) -> str:
    return url.replace("sqlite+aiosqlite://", "sqlite://", 1)


def _sync_postgres_url(url: str) -> str:
    """Use psycopg 3, which serves both sync and async, so one driver name covers both engines."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url.split("://", 1)[1]
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    return url


def _async_url(url: str) -> str:
    """Alembic's env.py builds an async engine, so it needs an async driver."""
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return _sync_postgres_url(url)
