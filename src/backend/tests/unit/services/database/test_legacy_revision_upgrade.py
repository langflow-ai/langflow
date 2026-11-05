"""Exercise the published 1.10.3 side branch on SQLite and PostgreSQL."""

from __future__ import annotations

import os
import sqlite3
from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from langflow.alembic.expand_compat import filter_sso_expand_diffs
from langflow.cli.integrity import check_schema
from langflow.cli.migration_preflight import check_version_direction
from langflow.services.database.revision import (
    LEGACY_BRANCH_POINT,
    DatabaseRevisionError,
    classify_revisions,
    script_directory,
)
from langflow.services.database.service import DatabaseService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

FIXTURES = Path(__file__).parents[3] / "data" / "upgrade_check"


def _restore_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript((FIXTURES / "langflow-1.10.3.sql").read_text())


def _restore_postgres(url: str, sqlite_path: Path, schema: str) -> None:
    engine = sa.create_engine(url)
    source = sa.create_engine(f"sqlite:///{sqlite_path}")
    try:
        ddl = (FIXTURES / "langflow-1.10.3-postgres-schema.sql").read_text().replace("public.", f'"{schema}".')
        with engine.begin() as connection:
            connection.exec_driver_sql(ddl)
            connection.execute(sa.text("SELECT set_config('search_path', :schema, false)"), {"schema": schema})
        source_metadata, target_metadata = sa.MetaData(), sa.MetaData()
        source_metadata.reflect(source)
        target_metadata.reflect(engine)
        with source.connect() as reader, engine.begin() as writer:
            for source_table in source_metadata.sorted_tables:
                rows = [dict(row) for row in reader.execute(source_table.select()).mappings()]
                if not rows:
                    continue
                target_table = target_metadata.tables[source_table.name]
                assert set(source_table.columns.keys()) <= set(target_table.columns.keys())
                for row in rows:
                    for column in target_table.columns:
                        if isinstance(column.type, sa.Uuid) and row.get(column.name) is not None:
                            row[column.name] = UUID(row[column.name])
                writer.execute(target_table.insert(), rows)
    finally:
        source.dispose()
        engine.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def databases(request, tmp_path):
    source_path = tmp_path / "source.db"
    _restore_sqlite(source_path)
    if request.param == "sqlite":
        yield f"sqlite+aiosqlite:///{source_path}", f"sqlite+aiosqlite:///{tmp_path / 'fresh.db'}"
        return
    url = os.getenv("LANGFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("set LANGFLOW_TEST_POSTGRES_URL for the PostgreSQL fixture")
    pytest.importorskip("psycopg")
    url = sa.make_url(url).set(drivername="postgresql+psycopg")
    admin = sa.create_engine(url)
    schemas = [f"revision_source_{uuid4().hex}", f"revision_fresh_{uuid4().hex}"]
    try:
        with admin.begin() as connection:
            for schema in schemas:
                connection.execute(sa.schema.CreateSchema(schema))
        urls = [
            url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
            for schema in schemas
        ]
        _restore_postgres(urls[0], source_path, schemas[0])
        yield tuple(urls)
    finally:
        with admin.begin() as connection:
            for schema in schemas:
                connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


def _service(url: str) -> DatabaseService:
    service = object.__new__(DatabaseService)
    service.database_url = url
    service.engine = create_async_engine(url)
    service.script_location = Path(__import__("langflow").__file__).parent / "alembic"
    service.settings_service = SimpleNamespace(settings=SimpleNamespace(database_connection_retry=False))
    service._open_alembic_log_buffer = lambda: nullcontext(StringIO())
    return service


async def _flows(service: DatabaseService) -> list:
    async with service.engine.connect() as connection:
        return (await connection.execute(sa.text("SELECT id, name, data, user_id FROM flow ORDER BY id"))).all()


async def test_1_10_3_upgrade_matches_a_fresh_schema_and_preserves_saved_flows(databases):
    source, fresh = (_service(url) for url in databases)
    try:
        original_flows = await _flows(source)
        await source.create_db_and_tables()
        await source.run_migrations()
        await fresh.create_db_and_tables()
        await fresh.run_migrations()
        async with source.engine.connect() as connection, fresh.engine.connect() as baseline:
            expected = sa.MetaData()
            await baseline.run_sync(lambda sync: expected.reflect(sync))
            # Model-created and migrated tables can name identical unique constraints differently.
            for table in expected.tables.values():
                for constraint in table.constraints:
                    if isinstance(constraint, sa.UniqueConstraint):
                        constraint.name = None
            # Apply the same explicit SSO EXPAND exceptions as the migration check.
            differences = await connection.run_sync(
                lambda sync: filter_sso_expand_diffs(compare_metadata(MigrationContext.configure(sync), expected))
            )
        assert not differences
        assert await _flows(source) == original_flows
        async with AsyncSession(source.engine) as session:
            assert (await check_schema(session)).status == "ok"
    finally:
        await source.engine.dispose()
        await fresh.engine.dispose()


async def test_read_only_checks_recognize_the_side_branch_without_migrating_it(databases):
    source = _service(databases[0])
    try:
        async with AsyncSession(source.engine) as session:
            version = await check_version_direction(session, script_directory().get_current_head())
            schema = await check_schema(session)
        assert version.status == "ok"
        assert schema.status == "fail"
        assert "supported Langflow 1.10.3 side branch" in version.summary
        assert schema.summary == version.summary
        assert (await source.validate_database_revision()).kind == "legacy"
    finally:
        await source.engine.dispose()


async def test_legacy_source_is_not_approved_for_its_earlier_branch_point(databases):
    source = _service(databases[0])
    try:
        original_flows = await _flows(source)
        async with AsyncSession(source.engine) as session:
            version = await check_version_direction(session, LEGACY_BRANCH_POINT)
        assert version.status == "fail"
        assert "1.10.3" in version.summary
        assert await _flows(source) == original_flows
        assert (await source.validate_database_revision()).kind == "legacy"
    finally:
        await source.engine.dispose()


async def test_unknown_revisions_have_the_same_restore_guidance_in_checks_and_startup(databases):
    source = _service(databases[0])
    try:
        async with source.engine.begin() as connection:
            await connection.execute(sa.text("UPDATE alembic_version SET version_num = 'future_revision'"))
        original = await _flows(source)
        async with AsyncSession(source.engine) as session:
            version = await check_version_direction(session, script_directory().get_current_head())
            schema = await check_schema(session)
        assert version.status == schema.status == "fail"
        assert version.summary == schema.summary == classify_revisions({"future_revision"}).message
        with pytest.raises(DatabaseRevisionError, match="restore-before-rolling-back"):
            await source.run_migrations()
        assert await _flows(source) == original
        async with source.engine.connect() as connection:
            assert (await connection.execute(sa.text("SELECT version_num FROM alembic_version"))).scalar_one() == (
                "future_revision"
            )
    finally:
        await source.engine.dispose()
