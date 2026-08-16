"""Upgrade and downgrade coverage for catalog policy storage."""

from __future__ import annotations

import importlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.catalog_policy import CatalogPolicyRule
from langflow.services.database.models.user.model import User
from sqlalchemy.dialects.postgresql import CITEXT as POSTGRESQL_CITEXT
from sqlalchemy.dialects.postgresql import UUID as POSTGRESQL_UUID

from .test_migration_execution import _engine_url, db_url  # noqa: F401

_MIGRATION = importlib.import_module("langflow.alembic.versions.d4a7c9e1b2f6_add_catalog_policy_rule")
_VALID_CHECKS = {
    "ck_catalog_policy_rule_resource_kind": "resource_kind IN ('component', 'template')",
    "ck_catalog_policy_rule_mode": "mode IN ('block', 'allow')",
    "ck_catalog_policy_rule_scope": "scope IN ('global', 'org', 'workspace')",
    "ck_catalog_policy_rule_scope_domain_consistency": (
        "(scope = 'global' AND domain_id IS NULL) OR (scope IN ('org', 'workspace') AND domain_id IS NOT NULL)"
    ),
}
_POSTGRES_REFLECTED_CHECKS = {
    "ck_catalog_policy_rule_resource_kind": (
        "((resource_kind)::text = ANY ((ARRAY['component'::character varying, 'template'::character varying])::text[]))"
    ),
    "ck_catalog_policy_rule_mode": (
        "((mode)::text = ANY ((ARRAY['block'::character varying, 'allow'::character varying])::text[]))"
    ),
    "ck_catalog_policy_rule_scope": (
        "((scope)::text = ANY "
        "((ARRAY['global'::character varying, 'org'::character varying, "
        "'workspace'::character varying])::text[]))"
    ),
    "ck_catalog_policy_rule_scope_domain_consistency": (
        "((((scope)::text = 'global'::text) AND (domain_id IS NULL)) "
        "OR (((scope)::text = ANY "
        "((ARRAY['org'::character varying, 'workspace'::character varying])::text[])) "
        "AND (domain_id IS NOT NULL)))"
    ),
}


def _add_existing_catalog_table(
    metadata: sa.MetaData,
    *,
    mode_default: str = "'block'",
    resource_key_type: sa.types.TypeEngine | None = None,
    created_at_default: str | None = None,
    updated_at_default: str | None = None,
    checks: dict[str, str] | None = None,
    extra_checks: tuple[tuple[str | None, str], ...] = (),
) -> sa.Table:
    return sa.Table(
        _MIGRATION.TABLE_NAME,
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_kind", sa.String(), nullable=False),
        sa.Column(
            "resource_key",
            resource_key_type if resource_key_type is not None else sa.String(),
            nullable=False,
        ),
        sa.Column("mode", sa.String(), nullable=False, server_default=sa.text(mode_default)),
        sa.Column("scope", sa.String(), nullable=False, server_default=sa.text("'global'")),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(created_at_default) if created_at_default is not None else sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(updated_at_default) if updated_at_default is not None else sa.func.now(),
        ),
        *(sa.CheckConstraint(sqltext, name=name) for name, sqltext in (checks or {}).items()),
        *(sa.CheckConstraint(sqltext, name=name) for name, sqltext in extra_checks),
    )


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
        assert _MIGRATION.down_revision == "e8f1a2b3c4d5"  # pragma: allowlist secret
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

        _MIGRATION.upgrade()
        row_count = connection.execute(sa.text("SELECT count(*) FROM catalog_policy_rule")).scalar_one()
        assert row_count == 0
        _MIGRATION.downgrade()


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


def test_catalog_policy_migration_rejects_missing_named_checks(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="missing required check constraints"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_permissive_named_checks(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        checks=dict.fromkeys(_VALID_CHECKS, "1 = 1"),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible check constraint"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_inverted_scope_domain_check(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    checks = {
        **_VALID_CHECKS,
        "ck_catalog_policy_rule_scope_domain_consistency": (
            "(scope = 'global' AND domain_id IS NOT NULL) OR (scope IN ('org', 'workspace') AND domain_id IS NULL)"
        ),
    }
    _add_existing_catalog_table(metadata, checks=checks)
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible check constraint"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_negated_named_checks(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        checks={name: f"({sqltext}) IS FALSE" for name, sqltext in _VALID_CHECKS.items()},
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible check constraint"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_preserves_cast_syntax_inside_quoted_identifier(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    checks = {
        **_VALID_CHECKS,
        "ck_catalog_policy_rule_mode": "\"mode::text\" IN ('block', 'allow')",
    }
    table = _add_existing_catalog_table(metadata, checks=checks)
    table.append_column(sa.Column("mode::text", sa.String(), nullable=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible check constraint"):
            _MIGRATION.upgrade()


@pytest.mark.parametrize("extra_check_name", ["ck_catalog_policy_rule_component_only", None])
def test_catalog_policy_migration_rejects_extra_overrestrictive_check(monkeypatch, extra_check_name):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        checks=_VALID_CHECKS,
        extra_checks=((extra_check_name, "resource_kind = 'component'"),),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible check constraint"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_duplicate_check_names(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        checks=_VALID_CHECKS,
        extra_checks=(("ck_catalog_policy_rule_resource_kind", "resource_kind = 'component'"),),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible check constraint"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_normalizes_postgresql_reflection_without_losing_structure():
    assert _MIGRATION._matches_check_contract(_POSTGRES_REFLECTED_CHECKS, _MIGRATION._BASELINE_CHECK_SQL)
    assert _MIGRATION._default_signature("'block'::character varying") == "'block'"
    assert (
        _MIGRATION._check_ast(
            "((resource_kind)::bpchar = ANY "
            "((ARRAY['component'::character varying, 'template'::character varying])::text[]))"
        )
        is None
    )


@pytest.mark.parametrize("option_name", ["not_valid", "no_inherit"])
def test_catalog_policy_migration_rejects_postgresql_check_behavior_options(option_name):
    class ReflectedCheckInspector:
        @staticmethod
        def get_check_constraints(_table_name):
            constraints = [{"name": name, "sqltext": sqltext} for name, sqltext in _POSTGRES_REFLECTED_CHECKS.items()]
            constraints[0]["dialect_options"] = {option_name: True}
            return constraints

    with pytest.raises(RuntimeError, match="incompatible check constraint"):
        _MIGRATION._validate_check_constraints(ReflectedCheckInspector())


@pytest.mark.parametrize(
    "mode_default",
    [
        "'allow'",
        "(substr('block', 1, 4))",
        "upper('block')",
        "(char(97, 108, 108, 111, 119) || substr('block', 6))",
    ],
)
def test_catalog_policy_migration_rejects_incompatible_mode_default(monkeypatch, mode_default):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        mode_default=mode_default,
        checks=_VALID_CHECKS,
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="mode has an incompatible default"):
            _MIGRATION.upgrade()


@pytest.mark.parametrize(
    "resource_key_type",
    [sa.Integer(), sa.String(1)],
    ids=["integer", "bounded-string"],
)
def test_catalog_policy_migration_rejects_incompatible_column_type(monkeypatch, resource_key_type):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        resource_key_type=resource_key_type,
        checks=_VALID_CHECKS,
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="resource_key has an incompatible type"):
            _MIGRATION.upgrade()


@pytest.mark.parametrize("created_at_default", ["'not-a-timestamp'", "'now'"])
def test_catalog_policy_migration_rejects_incompatible_timestamp_default(monkeypatch, created_at_default):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        created_at_default=created_at_default,
        checks=_VALID_CHECKS,
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="created_at has an incompatible default"):
            _MIGRATION.upgrade()


@pytest.mark.parametrize("required_default", [None, "NULL"])
def test_catalog_policy_migration_rejects_unknown_required_column(monkeypatch, required_default):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    table = _add_existing_catalog_table(metadata, checks=_VALID_CHECKS)
    table.append_column(
        sa.Column(
            "required_tag",
            sa.String(),
            nullable=False,
            server_default=sa.text(required_default) if required_default is not None else None,
        )
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="unsupported required columns"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_recognizes_postgresql_uuid_type():
    assert _MIGRATION._column_type_signature(POSTGRESQL_UUID(), dialect_name="postgresql") == "uuid"
    assert (
        _MIGRATION._column_type_signature(POSTGRESQL_CITEXT(), dialect_name="postgresql")
        == "string:case-insensitive:citext"
    )
    assert _MIGRATION._column_type_signature(sa.CHAR(32), dialect_name="postgresql") == "char:32"
    assert _MIGRATION._column_type_signature(sa.CHAR(32), dialect_name="sqlite") == "uuid"
    assert _MIGRATION._column_type_signature(sa.DateTime(timezone=True), dialect_name="postgresql") == "datetime:tz"
    assert _MIGRATION._column_type_signature(sa.DateTime(timezone=False), dialect_name="postgresql") == "datetime"


def test_catalog_policy_migration_rejects_case_insensitive_resource_key_collation(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    _add_existing_catalog_table(
        metadata,
        resource_key_type=sa.String(collation="NOCASE"),
        checks=_VALID_CHECKS,
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible case-insensitive collation"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_case_insensitive_unique_index(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)
        _MIGRATION.upgrade()
        operations.drop_index(_MIGRATION.UNSCOPED_INDEX, table_name=_MIGRATION.TABLE_NAME)
        connection.exec_driver_sql(
            """
            CREATE UNIQUE INDEX uq_catalog_policy_rule_unscoped
            ON catalog_policy_rule (
                resource_kind,
                resource_key COLLATE [NOCASE],
                scope
            )
            WHERE domain_id IS NULL
            """
        )

        with pytest.raises(RuntimeError, match="incompatible case-insensitive collation"):
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


def test_catalog_policy_migration_rejects_extra_unique_index(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)
        _MIGRATION.upgrade()
        operations.create_index(
            "uq_catalog_policy_rule_resource_kind_only",
            _MIGRATION.TABLE_NAME,
            ["resource_kind"],
            unique=True,
        )

        with pytest.raises(RuntimeError, match="incompatible unique index"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_extra_unique_constraint(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    table = _add_existing_catalog_table(metadata, checks=_VALID_CHECKS)
    sa.UniqueConstraint(table.c.resource_kind, name="uq_catalog_policy_rule_resource_kind_only")
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible unique constraint"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_extra_foreign_key(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    catalog_key = sa.Table("catalog_key", metadata, sa.Column("key", sa.String(), primary_key=True))
    table = _add_existing_catalog_table(metadata, checks=_VALID_CHECKS)
    sa.ForeignKeyConstraint(
        [table.c.resource_key],
        [catalog_key.c.key],
        name="fk_catalog_policy_rule_resource_key",
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)

        with pytest.raises(RuntimeError, match="incompatible foreign key contract"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_wrong_foreign_key_schema():
    class ReflectedForeignKeyInspector:
        @staticmethod
        def get_foreign_keys(_table_name):
            return [
                {
                    "constrained_columns": ["created_by"],
                    "referred_schema": "shadow",
                    "referred_table": "user",
                    "referred_columns": ["id"],
                    "options": {"ondelete": "SET NULL"},
                }
            ]

    with pytest.raises(RuntimeError, match="incompatible foreign key contract"):
        _MIGRATION._validate_foreign_keys(ReflectedForeignKeyInspector())


@pytest.mark.parametrize(
    "predicate",
    [
        "domain_id IS NULL AND 0 = 1",
        "domain_id IS 'NULL'",
        "'domain_id' IS NULL",
    ],
)
def test_catalog_policy_migration_rejects_adversarial_partial_predicate(monkeypatch, predicate):
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
            sqlite_where=sa.text(predicate),
        )

        with pytest.raises(RuntimeError, match="incompatible unique index contract"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_rejects_duplicates_before_repairing_index(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("user", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_MIGRATION, "op", operations)
        _MIGRATION.upgrade()
        operations.drop_index(_MIGRATION.UNSCOPED_INDEX, table_name=_MIGRATION.TABLE_NAME)
        for rule_id in (uuid4(), uuid4()):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog_policy_rule (id, resource_kind, resource_key)
                    VALUES (:id, 'component', 'OpenAIModel')
                    """
                ),
                {"id": rule_id.hex},
            )

        with pytest.raises(RuntimeError, match="duplicate rows"):
            _MIGRATION.upgrade()


def test_catalog_policy_migration_accepts_model_created_table_without_writes(db_url, monkeypatch):  # noqa: F811
    """Exercise the production create_all-before-Alembic ordering."""
    engine = sa.create_engine(_engine_url(db_url))
    try:
        User.__table__.create(engine, checkfirst=True)
        CatalogPolicyRule.__table__.create(engine, checkfirst=True)

        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(_MIGRATION, "op", operations)

            _MIGRATION.upgrade()
            _MIGRATION.upgrade()

            row_count = connection.execute(sa.text("SELECT count(*) FROM catalog_policy_rule")).scalar_one()
            assert row_count == 0
    finally:
        engine.dispose()
