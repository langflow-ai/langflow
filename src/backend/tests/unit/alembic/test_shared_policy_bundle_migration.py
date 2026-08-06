"""SQLite contract tests for the shared policy-bundle migration."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = Path(__file__).parents[3] / "base/langflow/alembic/versions/f7a9c2d4e6b8_add_shared_policy_bundle.py"


def _load_migration():
    assert _MIGRATION_PATH.exists(), "the shared policy-bundle migration has not been added"
    spec = importlib.util.spec_from_file_location("shared_policy_bundle_migration", _MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_legacy_policy_tables(connection: sa.Connection) -> tuple[sa.Table, sa.Table]:
    """Create the two pre-bundle stores as they exist at the migration boundary."""
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    provider_policy = sa.Table(
        "model_provider_policy",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("approved_provider_ids", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    catalog_policy = sa.Table(
        "catalog_policy_rule",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_kind", sa.String(), nullable=False),
        sa.Column("resource_key", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    metadata.create_all(connection)
    return provider_policy, catalog_policy


def _reflect_bundle_tables(connection: sa.Connection) -> tuple[sa.Table, sa.Table]:
    metadata = sa.MetaData()
    return (
        sa.Table("policy_bundle_revision", metadata, autoload_with=connection),
        sa.Table("policy_bundle_active", metadata, autoload_with=connection),
    )


def _reflect_revision_table(connection: sa.Connection) -> sa.Table:
    return sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)


def test_migration_backfills_one_active_revision_idempotently_and_preserves_legacy_tables(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        provider_policy, catalog_policy = _create_legacy_policy_tables(connection)
        scoped_domain_id = uuid4()
        legacy_rows = [
            {
                "id": uuid4(),
                "resource_kind": "component",
                "resource_key": "OpenAIModel",
                "mode": "block",
                "scope": "global",
            },
            {
                "id": uuid4(),
                "resource_kind": "component",
                "resource_key": "Case-Sensitive",
                "mode": "block",
                "scope": "global",
            },
            {
                "id": uuid4(),
                "resource_kind": "template",
                "resource_key": "starter-template",
                "mode": "block",
                "scope": "global",
            },
            {
                "id": uuid4(),
                "resource_kind": "component",
                "resource_key": "reserved-allow-row",
                "mode": "allow",
                "scope": "global",
            },
            {
                "id": uuid4(),
                "resource_kind": "template",
                "resource_key": "reserved-scoped-row",
                "mode": "block",
                "scope": "workspace",
                "domain_id": scoped_domain_id,
            },
        ]
        connection.execute(
            provider_policy.insert(),
            {"id": 1, "approved_provider_ids": ["openai", "anthropic"], "version": 7},
        )
        connection.execute(catalog_policy.insert(), legacy_rows)

        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()
        migration.upgrade()

        inspector = sa.inspect(connection)
        assert {"policy_bundle_revision", "policy_bundle_active"} <= set(inspector.get_table_names())
        history, active = _reflect_bundle_tables(connection)
        history_rows = list(connection.execute(sa.select(history)).mappings())
        active_rows = list(connection.execute(sa.select(active)).mappings())

        assert len(history_rows) == 1
        assert len(active_rows) == 1
        initial = history_rows[0]
        assert initial["revision"] == 7
        assert bool(initial["initialized"]) is True
        assert active_rows[0]["id"] == 1
        assert active_rows[0]["revision"] == initial["revision"]
        assert bool(active_rows[0]["initialized"]) is True
        assert initial["approved_provider_ids"] == ["anthropic", "openai"]
        assert initial["blocked_component_keys"] == ["Case-Sensitive", "OpenAIModel"]
        assert initial["blocked_template_keys"] == ["starter-template"]
        assert re.fullmatch(r"[0-9a-f]{64}", initial["content_hash"])
        assert initial["source"] == "migration"
        assert initial["created_by"] is None
        assert initial["created_at"] is not None
        assert initial["rollback_of_revision"] is None

        # Reserved allow/scoped rows are outside the initial global-block snapshot,
        # but migration to the additive bundle must not delete or rewrite them.
        assert connection.execute(sa.select(sa.func.count()).select_from(provider_policy)).scalar_one() == 1
        assert connection.execute(sa.select(sa.func.count()).select_from(catalog_policy)).scalar_one() == 5
        preserved = set(
            connection.execute(
                sa.select(
                    catalog_policy.c.resource_kind,
                    catalog_policy.c.resource_key,
                    catalog_policy.c.mode,
                    catalog_policy.c.scope,
                )
            ).tuples()
        )
        assert preserved == {
            (row["resource_kind"], row["resource_key"], row["mode"], row["scope"]) for row in legacy_rows
        }

        # Immutable history may retain an actor after its user row is deleted.
        # The legacy catalog table has a user FK, so rollback must not copy a
        # potentially dangling actor UUID into recreated rules.
        connection.execute(history.update().values(created_by=str(uuid4())))
        migration.downgrade()
        migration.downgrade()

        remaining_tables = set(sa.inspect(connection).get_table_names())
        assert "policy_bundle_revision" not in remaining_tables
        assert "policy_bundle_active" not in remaining_tables
        assert {"model_provider_policy", "catalog_policy_rule"} <= remaining_tables
        assert connection.execute(sa.select(sa.func.count()).select_from(catalog_policy)).scalar_one() == 5
        recreated_global_blocks = connection.execute(
            sa.select(catalog_policy.c.created_by).where(
                catalog_policy.c.mode == "block",
                catalog_policy.c.scope == "global",
                catalog_policy.c.domain_id.is_(None),
            )
        ).scalars()
        assert list(recreated_global_blocks) == [None, None, None]


def test_migration_seeds_revision_one_for_a_pristine_legacy_install(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        provider_policy, _catalog_policy = _create_legacy_policy_tables(connection)
        connection.execute(
            provider_policy.insert(),
            {"id": 1, "approved_provider_ids": [], "version": 0},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        history, active = _reflect_bundle_tables(connection)
        initial = connection.execute(sa.select(history)).mappings().one()
        assert initial["revision"] == 1
        assert bool(initial["initialized"]) is False
        active_row = connection.execute(sa.select(active)).mappings().one()
        assert active_row["revision"] == 1
        assert bool(active_row["initialized"]) is False
        assert initial["source"] == "migration"
        assert initial["approved_provider_ids"] == []
        assert initial["blocked_component_keys"] == []
        assert initial["blocked_template_keys"] == []

        migration.downgrade()
        legacy = connection.execute(sa.select(provider_policy)).mappings().one()
        assert legacy["version"] == 0

        migration.upgrade()
        _history, active = _reflect_bundle_tables(connection)
        active_row = connection.execute(sa.select(active)).mappings().one()
        assert active_row["revision"] == 1
        assert bool(active_row["initialized"]) is False


def test_migration_repairs_an_empty_revision_table_left_by_interrupted_sqlite_ddl(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        provider_policy, _catalog_policy = _create_legacy_policy_tables(connection)
        connection.execute(
            provider_policy.insert(),
            {"id": 1, "approved_provider_ids": [], "version": 0},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration._create_revision_table()
        assert "policy_bundle_revision" in sa.inspect(connection).get_table_names()
        assert "policy_bundle_active" not in sa.inspect(connection).get_table_names()

        migration.upgrade()

        history, active = _reflect_bundle_tables(connection)
        assert connection.execute(sa.select(sa.func.count()).select_from(history)).scalar_one() == 1
        active_row = connection.execute(sa.select(active)).mappings().one()
        assert active_row["revision"] == 1
        assert bool(active_row["initialized"]) is False


def test_migration_refuses_a_partial_bundle_schema_with_durable_revision_history(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        provider_policy, _catalog_policy = _create_legacy_policy_tables(connection)
        connection.execute(
            provider_policy.insert(),
            {"id": 1, "approved_provider_ids": [], "version": 0},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration._create_revision_table()
        history = _reflect_revision_table(connection)
        connection.execute(
            history.insert(),
            {
                "revision": 1,
                "initialized": False,
                "approved_provider_ids": [],
                "blocked_component_keys": [],
                "blocked_template_keys": [],
                "content_hash": migration._canonical_hash([], [], []),
                "source": "migration",
            },
        )

        with pytest.raises(RuntimeError, match="partially initialized with durable data"):
            migration.upgrade()

        assert "policy_bundle_active" not in sa.inspect(connection).get_table_names()


def test_migration_refuses_an_active_pointer_to_a_missing_revision(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        provider_policy, _catalog_policy = _create_legacy_policy_tables(connection)
        connection.execute(
            provider_policy.insert(),
            {"id": 1, "approved_provider_ids": [], "version": 0},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration._create_revision_table()
        migration._create_active_table()
        _history, active = _reflect_bundle_tables(connection)
        connection.execute(active.insert(), {"id": 1, "revision": 99, "initialized": True})

        with pytest.raises(RuntimeError, match="points to a missing immutable revision"):
            migration.upgrade()


def test_downgrade_refuses_revision_history_without_an_active_pointer(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        _create_legacy_policy_tables(connection)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration._create_revision_table()
        migration._create_active_table()
        history, _active = _reflect_bundle_tables(connection)
        connection.execute(
            history.insert(),
            {
                "revision": 1,
                "initialized": False,
                "approved_provider_ids": [],
                "blocked_component_keys": [],
                "blocked_template_keys": [],
                "content_hash": migration._canonical_hash([], [], []),
                "source": "migration",
            },
        )

        with pytest.raises(RuntimeError, match="immutable revision history but no active singleton"):
            migration.downgrade()

        assert {migration.REVISION_TABLE, migration.ACTIVE_TABLE} <= set(sa.inspect(connection).get_table_names())


def test_downgrade_refuses_an_active_pointer_to_a_missing_revision(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        _create_legacy_policy_tables(connection)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration._create_revision_table()
        migration._create_active_table()
        _history, active = _reflect_bundle_tables(connection)
        connection.execute(active.insert(), {"id": 1, "revision": 99, "initialized": True})

        with pytest.raises(RuntimeError, match="points to a missing immutable revision"):
            migration.downgrade()

        assert {migration.REVISION_TABLE, migration.ACTIVE_TABLE} <= set(sa.inspect(connection).get_table_names())


@pytest.mark.parametrize("lone_table", ["revision", "active"])
def test_downgrade_removes_an_empty_lone_bundle_table(monkeypatch, lone_table):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        if lone_table == "revision":
            migration._create_revision_table()
            table_name = migration.REVISION_TABLE
        else:
            migration._create_active_table()
            table_name = migration.ACTIVE_TABLE

        migration.downgrade()

        assert table_name not in sa.inspect(connection).get_table_names()


@pytest.mark.parametrize("lone_table", ["revision", "active"])
def test_downgrade_refuses_to_discard_a_populated_lone_bundle_table(monkeypatch, lone_table):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        if lone_table == "revision":
            migration._create_revision_table()
            history = _reflect_revision_table(connection)
            connection.execute(
                history.insert(),
                {
                    "revision": 1,
                    "initialized": False,
                    "approved_provider_ids": [],
                    "blocked_component_keys": [],
                    "blocked_template_keys": [],
                    "content_hash": migration._canonical_hash([], [], []),
                    "source": "migration",
                },
            )
            table_name = migration.REVISION_TABLE
        else:
            migration._create_active_table()
            metadata = sa.MetaData()
            active = sa.Table(migration.ACTIVE_TABLE, metadata, autoload_with=connection)
            connection.execute(active.insert(), {"id": 1, "revision": 1, "initialized": False})
            table_name = migration.ACTIVE_TABLE

        with pytest.raises(RuntimeError, match="partially initialized with durable data"):
            migration.downgrade()

        assert table_name in sa.inspect(connection).get_table_names()
