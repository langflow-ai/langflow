"""MySQL/MariaDB compatibility contracts for the Langflow schema.

These checks compile the models against the MySQL dialect (also used for
MariaDB) without a server, and pin the rules each MariaDB startup failure
broke: VARCHAR without a length, index keys over 3072 bytes, CHECK constraints
on AUTO_INCREMENT columns, expression indexes, and LIMIT inside IN subqueries.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import langflow
import pytest
import sqlalchemy as sa
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.service import (  # also registers every model
    DatabaseService,
    _normalize_sync_postgres_url,
)
from langflow.services.database.utils import (
    SKIP_ON_MYSQL_INFO_KEY,
    insert_ignoring_conflicts,
    materialize_subquery,
    update_returning,
    upsert,
)
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlmodel import SQLModel

MYSQL = mysql.dialect()
# InnoDB with DYNAMIC rows caps an index key at 3072 bytes; utf8mb4 uses 4 bytes per char.
MAX_INDEX_KEY_BYTES = 3072
UTF8MB4_BYTES_PER_CHAR = 4
# Generous upper bound for the non-string types used in indexes (CHAR(32) UUIDs, datetimes, ints).
NON_STRING_KEY_BYTES = 128

TABLES = SQLModel.metadata.sorted_tables


def _mysql_type(column: sa.Column) -> sa.types.TypeEngine:
    return column.type.dialect_impl(MYSQL)


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_create_table_compiles_on_mysql(table: sa.Table):
    sa.schema.CreateTable(table).compile(dialect=MYSQL)


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_index_keys_fit_mysql_limit(table: sa.Table):
    for index in table.indexes:
        if index.info.get(SKIP_ON_MYSQL_INFO_KEY):
            continue
        prefix_lengths = index.dialect_options["mysql"].get("length") or {}
        key_bytes = 0
        for column in index.columns:
            column_type = _mysql_type(column)
            if isinstance(column_type, sa.String) and not isinstance(column_type, sa.Text):
                chars = prefix_lengths.get(column.name, column_type.length)
                key_bytes += chars * UTF8MB4_BYTES_PER_CHAR
            else:
                key_bytes += NON_STRING_KEY_BYTES
        assert key_bytes <= MAX_INDEX_KEY_BYTES, (
            f"{table.name}.{index.name} needs {key_bytes} bytes; set mysql_length for its long string columns"
        )


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_expression_indexes_are_skipped_on_mysql(table: sa.Table):
    for index in table.indexes:
        if any(not isinstance(expression, sa.Column) for expression in index.expressions):
            assert index.info.get(SKIP_ON_MYSQL_INFO_KEY), (
                f"{table.name}.{index.name} is an expression index; wrap it with skip_index_on_mysql()"
            )
            ddl = sa.schema.CreateTable(table).compile(dialect=MYSQL)
            assert str(index.name) not in str(ddl)


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_no_check_constraint_on_auto_increment_column(table: sa.Table):
    # MariaDB rejects a CHECK constraint that references an AUTO_INCREMENT column.
    auto_increment = table.autoincrement_column
    if auto_increment is None:
        return
    for constraint in table.constraints:
        if isinstance(constraint, sa.CheckConstraint):
            assert auto_increment.name not in str(constraint.sqltext), (
                f"{table.name}.{auto_increment.name} is AUTO_INCREMENT on MySQL and is used by "
                f"{constraint.name}; declare it with autoincrement=False if the application assigns it"
            )


def test_materialize_subquery_keeps_limit_out_of_in_clause():
    keep_newest = (
        sa.select(TransactionTable.id).order_by(TransactionTable.timestamp.desc()).offset(3).limit(10)  # type: ignore[attr-defined]
    )
    statement = sa.delete(TransactionTable).where(TransactionTable.id.in_(materialize_subquery(keep_newest)))  # type: ignore[attr-defined]

    sql = " ".join(str(statement.compile(dialect=MYSQL)).split())

    # MariaDB error 1235: LIMIT directly inside an IN subquery is unsupported.
    assert "IN (SELECT anon_1.id FROM (SELECT transaction.id" in sql
    assert "LIMIT" in sql


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("mysql://u:p@db:3306/langflow", "mysql+aiomysql://u:p@db:3306/langflow"),
        ("mysql+pymysql://u:p@db:3306/langflow", "mysql+aiomysql://u:p@db:3306/langflow"),
        ("mysql+aiomysql://u:p@db:3306/langflow", "mysql+aiomysql://u:p@db:3306/langflow"),
        ("mariadb://u:p@db:3306/langflow", "mysql+aiomysql://u:p@db:3306/langflow"),
    ],
)
def test_mysql_urls_use_the_async_driver(configured: str, expected: str):
    holder = SimpleNamespace(database_url=configured)
    DatabaseService._sanitize_database_url(holder)  # type: ignore[arg-type]
    assert holder.database_url == expected


def test_sync_url_for_mysql_uses_pymysql():
    assert _normalize_sync_postgres_url("mysql+aiomysql://u:p@db/langflow") == "mysql+pymysql://u:p@db/langflow"


# --- MariaDB has no UPDATE ... RETURNING and no ON CONFLICT -------------------------------------

LANGFLOW_PACKAGE = Path(langflow.__file__).parent
# Functions that only ever run on SQLite/PostgreSQL (guarded by a dialect check) may use ON CONFLICT.
ON_CONFLICT_ALLOWED = {
    ("services/database/utils.py", "upsert"),
    ("services/database/utils.py", "insert_ignoring_conflicts"),
    ("services/database/models/jobs/metrics.py", "prepare_retention_metrics"),  # SQLite-only branch
    ("services/triggers/ledger.py", "append_event"),  # SQLite-only branch
    ("services/triggers/ledger.py", "append_events"),  # after a sqlite/postgresql guard
    ("services/triggers/listeners/connection_leases.py", "_claim_sqlite"),
    ("services/database/sqlite_to_postgres.py", "*"),  # PostgreSQL target only
}


def _package_functions():
    for path in LANGFLOW_PACKAGE.rglob("*.py"):
        relative = path.relative_to(LANGFLOW_PACKAGE).as_posix()
        if relative.startswith("alembic/versions/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                yield relative, function


# Functions that only reach UPDATE ... RETURNING after checking dialect.update_returning.
UPDATE_RETURNING_ALLOWED = {
    ("services/database/utils.py", "update_returning"),
    ("services/database/models/deployment/crud.py", "update_deployment_metadata_batch"),
    ("services/triggers/listeners/connection_leases.py", "_claim_sqlite"),  # SQLite-only INSERT ... ON CONFLICT
}


def test_no_update_returning_outside_the_helper():
    offenders = []
    for relative, function in _package_functions():
        if (relative, function.name) in UPDATE_RETURNING_ALLOWED:
            continue
        offenders.extend(
            f"{relative}:{node.lineno} ({function.name})"
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "returning"
            and "update(" in ast.unparse(node.func.value)
        )
    assert not offenders, f"use update_returning(); MariaDB has no UPDATE ... RETURNING: {offenders}"


def test_on_conflict_only_in_dialect_guarded_code():
    offenders = []
    for relative, function in _package_functions():
        if (relative, function.name) in ON_CONFLICT_ALLOWED or (relative, "*") in ON_CONFLICT_ALLOWED:
            continue
        offenders.extend(
            f"{relative}:{node.lineno} ({function.name})"
            for node in ast.walk(function)
            if isinstance(node, ast.Attribute) and node.attr.startswith("on_conflict_do_")
        )
    assert not offenders, f"use upsert()/insert_ignoring_conflicts(); MySQL has no ON CONFLICT: {offenders}"


class _Base(DeclarativeBase):
    pass


class _Counter(_Base):
    __tablename__ = "mysql_compat_counter"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(sa.String(32))
    hits: Mapped[int] = mapped_column(default=0)


@pytest.mark.parametrize("native_returning", [True, False], ids=["returning", "mariadb-fallback"])
async def test_update_returning_returns_the_updated_rows(monkeypatch, *, native_returning: bool):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    monkeypatch.setattr(engine.sync_engine.dialect, "update_returning", native_returning)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add_all([_Counter(id=1, owner="a"), _Counter(id=2, owner="a"), _Counter(id=3, owner="b")])
        await session.commit()

        rows = await update_returning(session, _Counter, _Counter.owner == "a", values={"hits": _Counter.hits + 5})
        missing = await update_returning(session, _Counter, _Counter.owner == "zzz", values={"hits": 1})
        await session.commit()

        assert sorted((row.id, row.hits) for row in rows) == [(1, 5), (2, 5)]
        assert missing == []
        untouched = (await session.execute(sa.select(_Counter.hits).where(_Counter.id == 3))).scalar_one()
        assert untouched == 0
    await engine.dispose()


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        (mysql.dialect(), "ON DUPLICATE KEY UPDATE"),
        (postgresql.dialect(), "ON CONFLICT"),
        (sqlite.dialect(), "ON CONFLICT"),
    ],
    ids=["mysql", "postgresql", "sqlite"],
)
def test_upsert_helpers_use_the_dialect_syntax(dialect, expected: str):
    table = _Counter.__table__
    upsert_sql = str(
        upsert(
            dialect.name,
            table,
            {"id": 1, "owner": "a", "hits": 1},
            index_elements=["id"],
            set_=lambda new: {"hits": table.c.hits + new.hits},
        ).compile(dialect=dialect)
    )
    ignore_sql = str(insert_ignoring_conflicts(dialect.name, table, [{"id": 1, "owner": "a"}]).compile(dialect=dialect))

    assert expected in upsert_sql
    assert expected in ignore_sql
    assert "IGNORE" not in ignore_sql.upper().split("ON")[0], "INSERT IGNORE would also swallow unrelated errors"
