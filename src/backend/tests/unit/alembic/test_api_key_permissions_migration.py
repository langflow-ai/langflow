"""Keep legacy keys unrestricted and refuse unsafe scope-support downgrades."""

import importlib
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

_MIGRATION = importlib.import_module("langflow.alembic.versions.a1e7b9c3d5f0_add_api_key_permissions")


@pytest.fixture(params=["sqlite", "postgresql"])
def migration_connection(request):
    url = "sqlite://"
    schema = None
    if request.param == "postgresql":
        url = os.environ.get("SCOPED_API_KEY_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("SCOPED_API_KEY_TEST_POSTGRES_URL is not configured")
        schema = f"scoped_key_migration_{uuid4().hex}"
    engine = sa.create_engine(url)
    try:
        with engine.begin() as connection:
            if schema:
                connection.execute(sa.schema.CreateSchema(schema))
                connection.execute(sa.text("SELECT set_config('search_path', :schema, true)"), {"schema": schema})
            yield connection
    finally:
        if schema:
            with engine.begin() as cleanup:
                cleanup.execute(sa.schema.DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()


def test_api_key_permission_migration_keeps_one_release_head():
    from pathlib import Path

    scripts = ScriptDirectory(str(Path(_MIGRATION.__file__).parents[1]))
    assert scripts.get_heads() == [_MIGRATION.revision]


def test_api_key_permission_migration_preserves_legacy_and_roundtrips(monkeypatch, migration_connection):
    connection = migration_connection
    metadata = sa.MetaData()
    keys = sa.Table(
        "apikey", metadata, sa.Column("id", sa.Integer(), primary_key=True), sa.Column("api_key", sa.String())
    )
    metadata.create_all(connection)
    connection.execute(keys.insert().values(id=1, api_key="legacy"))  # pragma: allowlist secret
    monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))
    _MIGRATION.upgrade()
    _MIGRATION.upgrade()
    columns = {column["name"]: column for column in sa.inspect(connection).get_columns("apikey")}
    assert columns["permissions"]["nullable"] is True
    assert connection.execute(sa.text("SELECT permissions FROM apikey WHERE id=1")).scalar() is None
    _MIGRATION.downgrade()
    assert "permissions" not in {column["name"] for column in sa.inspect(connection).get_columns("apikey")}
    assert connection.execute(sa.select(keys.c.api_key)).scalar_one() == "legacy"


def test_api_key_permission_migration_refuses_scoped_key_downgrade(monkeypatch, migration_connection):
    connection = migration_connection
    metadata = sa.MetaData()
    sa.Table("apikey", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(connection)
    monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))
    _MIGRATION.upgrade()
    connection.execute(
        sa.text("INSERT INTO apikey (id, permissions) VALUES (1, :policy)"), {"policy": '{"restrictions": []}'}
    )
    with pytest.raises(RuntimeError, match="Revoke restricted API keys"):
        _MIGRATION.downgrade()
    assert "permissions" in {column["name"] for column in sa.inspect(connection).get_columns("apikey")}


def test_legacy_key_policy_is_sql_null():
    from langflow.services.database.models.api_key.model import ApiKey

    column = ApiKey.__table__.c.permissions
    assert column.type.none_as_null is True
    assert column.nullable is True
