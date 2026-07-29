"""Upgrade and downgrade coverage for catalog policy storage."""

from __future__ import annotations

import importlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.d4a7c9e1b2f6_add_catalog_policy_rule")


def test_catalog_policy_migration_upgrades_idempotently_and_downgrades(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        _MIGRATION.upgrade()
        _MIGRATION.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns(_MIGRATION.TABLE_NAME)}
        indexes = {index["name"]: index for index in inspector.get_indexes(_MIGRATION.TABLE_NAME)}
        checks = {constraint["name"] for constraint in inspector.get_check_constraints(_MIGRATION.TABLE_NAME)}
        foreign_keys = inspector.get_foreign_keys(_MIGRATION.TABLE_NAME)

        assert _MIGRATION.revision == "d4a7c9e1b2f6"  # pragma: allowlist secret
        assert _MIGRATION.down_revision == "b7d5f9a3c2e4"  # pragma: allowlist secret
        assert set(columns) == {
            "id",
            "resource_kind",
            "resource_key",
            "mode",
            "scope",
            "domain_id",
            "created_by",
            "created_at",
            "updated_at",
        }
        assert columns["domain_id"]["nullable"] is True
        assert columns["created_by"]["nullable"] is True
        assert columns["created_at"]["nullable"] is False
        assert columns["updated_at"]["nullable"] is False
        assert indexes[_MIGRATION.SCOPED_INDEX]["column_names"] == [
            "resource_kind",
            "resource_key",
            "scope",
            "domain_id",
        ]
        assert indexes[_MIGRATION.UNSCOPED_INDEX]["column_names"] == [
            "resource_kind",
            "resource_key",
            "scope",
        ]
        assert indexes[_MIGRATION.SCOPED_INDEX]["unique"] == 1
        assert indexes[_MIGRATION.UNSCOPED_INDEX]["unique"] == 1
        assert checks == {
            "ck_catalog_policy_rule_resource_kind",
            "ck_catalog_policy_rule_mode",
            "ck_catalog_policy_rule_scope",
            "ck_catalog_policy_rule_scope_domain_consistency",
        }
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["constrained_columns"] == ["created_by"]
        assert foreign_keys[0]["referred_table"] == "user"
        assert foreign_keys[0]["options"]["ondelete"] == "SET NULL"

        rule_id = uuid4()
        connection.execute(
            sa.text(
                """
                INSERT INTO catalog_policy_rule (id, resource_kind, resource_key)
                VALUES (:id, 'component', 'OpenAIModel')
                """
            ),
            {"id": rule_id.hex},
        )
        stored = connection.execute(
            sa.text(
                """
                SELECT mode, scope, domain_id, created_at, updated_at
                FROM catalog_policy_rule
                WHERE id = :id
                """
            ),
            {"id": rule_id.hex},
        ).one()
        assert stored.mode == "block"
        assert stored.scope == "global"
        assert stored.domain_id is None
        assert stored.created_at is not None
        assert stored.updated_at is not None

        _MIGRATION.downgrade()
        _MIGRATION.downgrade()
        assert _MIGRATION.TABLE_NAME not in sa.inspect(connection).get_table_names()


def test_catalog_policy_migration_rejects_partial_existing_table(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table(
        _MIGRATION.TABLE_NAME,
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_kind", sa.String(), nullable=False),
        sa.Column("resource_key", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="missing required columns"):
            _MIGRATION.upgrade()

        assert _MIGRATION.TABLE_NAME in sa.inspect(connection).get_table_names()


def test_catalog_policy_migration_rejects_malformed_complete_table(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table(
        _MIGRATION.TABLE_NAME,
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_kind", sa.String(), nullable=False),
        sa.Column("resource_key", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default=sa.text("'block'")),
        sa.Column("scope", sa.String(), nullable=False, server_default=sa.text("'global'")),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *(sa.CheckConstraint("1 = 1", name=check_name) for check_name in _MIGRATION._REQUIRED_CHECKS),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="resource-kind checks"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_malformed_named_index(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)
        _MIGRATION.upgrade()

        operations.drop_index(_MIGRATION.SCOPED_INDEX, table_name=_MIGRATION.TABLE_NAME)
        operations.create_index(
            _MIGRATION.SCOPED_INDEX,
            _MIGRATION.TABLE_NAME,
            ["resource_kind"],
            unique=False,
        )

        with pytest.raises(RuntimeError, match="incompatible definition"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_adversarial_partial_predicate(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)
        _MIGRATION.upgrade()

        operations.drop_index(_MIGRATION.UNSCOPED_INDEX, table_name=_MIGRATION.TABLE_NAME)
        operations.create_index(
            _MIGRATION.UNSCOPED_INDEX,
            _MIGRATION.TABLE_NAME,
            ["resource_kind", "resource_key", "scope"],
            unique=True,
            sqlite_where=sa.text("domain_id IS NULL AND 0 = 1"),
        )

        with pytest.raises(RuntimeError, match="global NULL-safe uniqueness"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_overrestrictive_named_checks(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table(
        _MIGRATION.TABLE_NAME,
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_kind", sa.String(), nullable=False),
        sa.Column("resource_key", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default=sa.text("'block'")),
        sa.Column("scope", sa.String(), nullable=False, server_default=sa.text("'global'")),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "resource_kind = 'component'",
            name="ck_catalog_policy_rule_resource_kind",
        ),
        sa.CheckConstraint("mode = 'block'", name="ck_catalog_policy_rule_mode"),
        sa.CheckConstraint(
            "scope IN ('global', 'workspace')",
            name="ck_catalog_policy_rule_scope",
        ),
        sa.CheckConstraint(
            "(scope = 'global' AND domain_id IS NULL) OR (scope = 'workspace' AND domain_id IS NOT NULL)",
            name="ck_catalog_policy_rule_scope_domain_consistency",
        ),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="valid template rules"):
            _MIGRATION.upgrade()
