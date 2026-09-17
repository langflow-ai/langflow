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
    from collections.abc import Iterator, Mapping

# Postgres caps bind parameters per statement at 65535.
_MAX_PARAMS_PER_STATEMENT = 60_000
_VERSION_TABLE = "alembic_version"
_POLICY_HISTORY_TABLE = "policy_bundle_revision"
# How many offending rows a refusal names, enough to find the pattern.
_ROWS_NAMED = 10


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
    source_path = sa.engine.make_url(_sync_sqlite_url(source_url)).database
    if not source_path or not Path(source_path).is_file():
        # Checked up front because opening a missing SQLite file creates an empty one.
        report.problems.append(f"source database {source_path!r} does not exist")
        return report

    source = sa.create_engine(_sync_sqlite_url(source_url))
    try:
        head = _script_head()
        source_revision = _revision(source)
        report.revision = source_revision
        if source_revision is None:
            report.problems.append(
                "source database has no Langflow schema. If it is a copy, make it with sqlite3's .backup or "
                "VACUUM INTO: Langflow runs SQLite in WAL mode, and a plain cp can come out empty"
            )
            return report
        if source_revision != head:
            report.problems.append(
                f"source database is at revision {source_revision}, this Langflow expects {head}; "
                "start this Langflow version against the SQLite database once so it migrates, then convert"
            )
            return report

        models = _model_tables()
        target = sa.create_engine(_sync_postgres_url(target_url))
        try:
            # Everything that can refuse runs before the target is migrated, so a
            # refused run leaves the target exactly as it was.
            report.problems.extend(_preflight(source, target, models))
            if report.problems:
                return report
            upgrade_to_head(target_url)
            _convert(source, target, models, report, batch_size=batch_size)
        except sa.exc.SQLAlchemyError as exc:
            # Reported rather than raised: a traceback would print the target URL,
            # password included. The driver's own message never contains it.
            report.problems.append(f"could not use the target database: {_describe(exc)}")
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
        # JSON columns would otherwise store a JSON null, which IS NULL no longer matches.
        return sa.null() if isinstance(column_type, sa.JSON) else None
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
        elif not column_type.timezone and parsed.tzinfo is not None:
            # Rows written through raw SQL can keep an offset. Postgres would convert it to
            # the session time zone, which is not UTC on every server, so store UTC wall time.
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    if isinstance(column_type, sa.Date) and not isinstance(value, date):
        return date.fromisoformat(str(value))
    return value


def _preflight(source: sa.Engine, target: sa.Engine, models: Mapping[str, sa.Table]) -> list[str]:
    with source.connect() as src, target.connect() as tgt:
        return _invalid_enum_values(src, models) + _foreign_users(src, tgt)


def _convert(
    source: sa.Engine,
    target: sa.Engine,
    models: Mapping[str, sa.Table],
    report: ConversionReport,
    *,
    batch_size: int,
) -> None:
    metadata = sa.MetaData()
    metadata.reflect(bind=target)
    source_tables = set(sa.inspect(source).get_table_names())
    tables = [table for table in copy_order(metadata) if table.name in source_tables]

    with source.connect() as src:
        source_columns = {table.name: _source_columns(src, table.name) for table in tables}
        try:
            with target.begin() as tgt:
                _align_system_roles(src, tgt)
                if any(table.name == _POLICY_HISTORY_TABLE for table in tables):
                    _clear_seeded_policy_history(tgt)
                for table in tables:
                    columns = [column for column in table.columns if column.name in source_columns[table.name]]
                    source_rows = _copy_table(src, tgt, table, columns, models.get(table.name), batch_size=batch_size)
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
        except _CoercionError as exc:
            report.problems.append(f"copy failed and was rolled back: {exc}")
        except sa.exc.SQLAlchemyError as exc:
            report.problems.append(f"copy failed and was rolled back: {_describe(exc)}")


class _RollbackError(Exception):
    """Raised inside the copy transaction to roll it back after recording problems."""


class _CoercionError(Exception):
    """A source value the target column cannot take."""


def _describe(exc: sa.exc.SQLAlchemyError) -> str:
    cause = getattr(exc, "orig", None) or exc
    return f"{cause.__class__.__name__}: {str(cause).splitlines()[0]}"


def _coerce(value: Any, model_type: sa.types.TypeEngine | None, column: sa.Column) -> Any:
    try:
        return coerce_value(_enum_label(value, model_type), column.type)
    except (ValueError, TypeError) as exc:
        msg = f"{column.table.name}.{column.name} holds a value {column.type} cannot take: {exc}"
        raise _CoercionError(msg) from exc


def _source_columns(conn: sa.Connection, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table)}


def _model_tables() -> Mapping[str, sa.Table]:
    from sqlmodel import SQLModel

    import langflow.services.database.models  # noqa: F401 - importing registers every table on the metadata

    return SQLModel.metadata.tables


def _enum_type(column_type: sa.types.TypeEngine | None) -> sa.Enum | None:
    if isinstance(column_type, sa.types.TypeDecorator):
        column_type = column_type.impl_instance
    return column_type if isinstance(column_type, sa.Enum) else None


def _enum_label(value: Any, model_type: sa.types.TypeEngine | None) -> Any:
    """The enum label Langflow reads ``value`` as.

    Trace and span rows written before 1.9.2 hold enum names in any case, and
    SQLite rows were never rewritten. The model's column type maps those on
    read, so the copy uses the same mapping instead of refusing them.
    """
    if value is None or not isinstance(model_type, sa.types.TypeDecorator) or _enum_type(model_type) is None:
        return value
    try:
        return model_type.process_result_value(value, None).value
    except LookupError:
        return value


def _invalid_enum_values(conn: sa.Connection, models: Mapping[str, sa.Table]) -> list[str]:
    """Postgres enforces enum membership and SQLite does not, so check before writing anything.

    A bad value would otherwise fail only when its row is reached, partway through the copy.
    The enum labels come from the models, which match the migrated schema, so this
    runs before the target is touched.
    """
    problems = []
    source_tables = set(sa.inspect(conn).get_table_names())
    for table in models.values():
        if table.name not in source_tables:
            continue
        source_columns = _source_columns(conn, table.name)
        for column in table.columns:
            enum = _enum_type(column.type)
            if enum is None or column.name not in source_columns:
                continue
            allowed = set(enum.enums)
            quoted = f'"{column.name}"'
            found = conn.execute(sa.text(f'SELECT DISTINCT {quoted} FROM "{table.name}"')).scalars()  # noqa: S608
            bad = sorted(
                {value for value in found if value is not None and _enum_label(value, column.type) not in allowed}
            )
            if not bad:
                continue
            primary_key = ", ".join(f'"{key.name}"' for key in table.primary_key.columns)
            rows = conn.execute(
                sa.text(
                    f'SELECT {primary_key} FROM "{table.name}" WHERE {quoted} IN :bad LIMIT {_ROWS_NAMED}'  # noqa: S608
                ).bindparams(sa.bindparam("bad", expanding=True)),
                {"bad": bad},
            ).all()
            named = [row[0] if len(row) == 1 else tuple(row) for row in rows]
            problems.append(
                f"{table.name}.{column.name} holds {bad}, which {enum.name} does not allow "
                f"(allowed: {sorted(allowed)}); rows include {named}"
            )
    return problems


def _foreign_users(src: sa.Connection, tgt: sa.Connection) -> list[str]:
    """Refuse to merge two instances: the target may only hold users this source also has."""
    if not sa.inspect(tgt).has_table("user"):
        return []
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


def _clear_seeded_policy_history(tgt: sa.Connection) -> None:
    """Drop the target's seeded policy bundle history so the source's lands verbatim.

    The history is append-only, not a singleton, and the migration numbers its first
    revision from model_provider_policy.version. A source that changed its provider
    policy before upgrading starts above 1, so upserting on the revision would leave
    the target's seeded revision 1 behind. policy_bundle_active is upserted after this
    and points into the copied history.
    """
    tgt.execute(sa.text(f'DELETE FROM "{_POLICY_HISTORY_TABLE}"'))  # noqa: S608


def _copy_table(
    src: sa.Connection,
    tgt: sa.Connection,
    table: sa.Table,
    columns: list[sa.Column],
    model: sa.Table | None,
    *,
    batch_size: int,
) -> int:
    names = [column.name for column in columns]
    model_types = [
        model.columns[column.name].type if model is not None and column.name in model.columns else None
        for column in columns
    ]
    select_sql = sa.text(
        f'SELECT {", ".join(f"{chr(34)}{name}{chr(34)}" for name in names)} FROM "{table.name}"'  # noqa: S608
    )
    rows = (
        {
            column.name: _coerce(value, model_type, column)
            for column, model_type, value in zip(columns, model_types, raw, strict=True)
        }
        for raw in src.execute(select_sql)
    )
    if parent := _self_parent_column(table):
        rows = iter(_parents_first(list(rows), *parent))

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


def _parents_first(rows: list[dict[str, Any]], parent_column: str, key_column: str) -> list[dict[str, Any]]:
    """Order a self-referencing table so each row comes after the row it points at."""
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
    return ",".join(revisions)


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
