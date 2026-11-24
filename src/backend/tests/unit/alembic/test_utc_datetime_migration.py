"""Preserve historical timestamps when adopting SQLModel's UTC datetime type."""

import importlib
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import UTCDateTime

from .test_migration_execution import _engine_url, db_url  # noqa: F401

_MIGRATION = importlib.import_module("langflow.alembic.versions.f2a7c9e4b681_adopt_utc_datetime_storage")
_UTC = datetime(2024, 11, 3, 8, 30, 12, 345678, tzinfo=timezone.utc)


@pytest.mark.parametrize("already_aware", [False, True])
def test_timestamp_upgrade_and_downgrade_preserve_values(db_url, already_aware):  # noqa: F811
    """Exercise every column, NULLs, idempotency, and a non-UTC PostgreSQL session."""
    engine = sa.create_engine(_engine_url(db_url))
    postgres = engine.dialect.name == "postgresql"
    metadata = sa.MetaData()
    tables = [
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            *(sa.Column(column, sa.DateTime(timezone=already_aware)) for column in columns),
            sa.Column("unrelated_timestamp", sa.DateTime()),
        )
        for name, columns in _MIGRATION._TIMESTAMP_COLUMNS.items()
    ]
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            if postgres:
                connection.execute(sa.text("SET LOCAL TIME ZONE 'America/Los_Angeles'"))
            original = _UTC if already_aware and postgres else _UTC.replace(tzinfo=None)
            for table in tables:
                names = _MIGRATION._TIMESTAMP_COLUMNS[table.name]
                connection.execute(
                    table.insert(),
                    [
                        {"id": 1, **dict.fromkeys(names, original), "unrelated_timestamp": _UTC.replace(tzinfo=None)},
                        {"id": 2, **dict.fromkeys(names, None), "unrelated_timestamp": None},
                    ],
                )

            with Operations.context(MigrationContext.configure(connection)):
                _MIGRATION.upgrade()
                _MIGRATION.upgrade()
            for table in tables:
                names = _MIGRATION._TIMESTAMP_COLUMNS[table.name]
                columns = {column["name"]: column for column in sa.inspect(connection).get_columns(table.name)}
                if postgres:
                    assert all(columns[name]["type"].timezone for name in names)
                    assert not columns["unrelated_timestamp"]["type"].timezone
                # The ORM must recover aware UTC even from historical SQLite values.
                statement = sa.select(*(sa.type_coerce(table.c[name], UTCDateTime()) for name in names)).order_by(
                    table.c.id
                )
                rows = connection.execute(statement).all()
                assert tuple(rows[0]) == (_UTC,) * len(names)
                assert all(value.utcoffset() == timedelta(0) for value in rows[0])
                assert tuple(rows[1]) == (None,) * len(names)

            with Operations.context(MigrationContext.configure(connection)):
                _MIGRATION.downgrade()
                _MIGRATION.downgrade()
            for table in tables:
                names = _MIGRATION._TIMESTAMP_COLUMNS[table.name]
                rows = connection.execute(sa.select(table).order_by(table.c.id)).mappings().all()
                assert [row["id"] for row in rows] == [1, 2]
                assert all(rows[0][name] == _UTC.replace(tzinfo=None) for name in names)
                assert all(rows[1][name] is None for name in names)
                assert rows[0]["unrelated_timestamp"] == _UTC.replace(tzinfo=None)
    finally:
        engine.dispose()


def test_timestamp_migration_handles_missing_tables_and_columns(db_url):  # noqa: F811
    engine = sa.create_engine(_engine_url(db_url))
    try:
        metadata = sa.MetaData()
        sa.Table("user", metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)
        with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            _MIGRATION.upgrade()
            _MIGRATION.downgrade()
            assert sa.inspect(connection).get_table_names() == ["user"]
    finally:
        engine.dispose()
