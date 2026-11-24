"""Contract tests for nullable environment-variable origin tracking."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).parents[3] / "base/langflow/alembic/versions/d7e9f1a3b5c8_add_variable_environment_origin.py"
)


def test_variable_origin_migration_preserves_values_and_old_inserts(monkeypatch):
    """Upgrade/downgrade is repeatable and old workers can omit the nullable column."""
    spec = importlib.util.spec_from_file_location("variable_environment_origin", _MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        old_variable = sa.Table(
            "variable",
            sa.MetaData(),
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("value", sa.String(), nullable=False),
        )
        old_variable.create(connection)
        connection.execute(old_variable.insert().values(id=1, value="legacy-ciphertext"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        migration.upgrade()
        connection.execute(old_variable.insert().values(id=2, value="old-worker-ciphertext"))
        variable = sa.Table("variable", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(sa.select(variable).order_by(variable.c.id)).mappings().all()
        assert [row["value"] for row in rows] == ["legacy-ciphertext", "old-worker-ciphertext"]
        assert [row["is_environment_managed"] for row in rows] == [None, None]
        assert variable.c.is_environment_managed.nullable
        connection.execute(variable.update().where(variable.c.id == 1).values(is_environment_managed=True))
        connection.execute(variable.update().where(variable.c.id == 2).values(is_environment_managed=False))
        assert connection.execute(
            sa.select(variable.c.is_environment_managed).order_by(variable.c.id)
        ).scalars().all() == [
            True,
            False,
        ]
        migration.downgrade()
        migration.downgrade()
        assert "is_environment_managed" not in {c["name"] for c in sa.inspect(connection).get_columns("variable")}
        assert connection.execute(sa.select(old_variable.c.value).order_by(old_variable.c.id)).scalars().all() == [
            "legacy-ciphertext",
            "old-worker-ciphertext",
        ]
    engine.dispose()
