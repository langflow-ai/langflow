"""Add catalog policy rules for component and template governance.

Phase: EXPAND
Revision ID: d4a7c9e1b2f6
Revises: b7d5f9a3c2e4
Create Date: 2026-07-29 00:00:00.000000

The table is empty by default, preserving the existing default-allow catalog
behavior. P1 writes only global block rules; ``allow`` mode and scoped domains
are reserved so later phases can add behavior without replacing the schema.

Downgrade drops the table and all catalog-policy state. Back up policy rows
before downgrading if they will be needed after a future roll-forward.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlmodel.sql.sqltypes import AutoString

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d4a7c9e1b2f6"  # pragma: allowlist secret
down_revision: str | None = "b7d5f9a3c2e4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "catalog_policy_rule"
SCOPED_INDEX = "uq_catalog_policy_rule_scoped"
UNSCOPED_INDEX = "uq_catalog_policy_rule_unscoped"
_REQUIRED_INDEX_COLUMNS = (
    "resource_kind",
    "resource_key",
    "scope",
    "domain_id",
)
_SQLITE_UUID_LENGTH = 32
_REQUIRED_COLUMNS = {
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
_REQUIRED_CHECKS = {
    "ck_catalog_policy_rule_resource_kind",
    "ck_catalog_policy_rule_mode",
    "ck_catalog_policy_rule_scope",
    "ck_catalog_policy_rule_scope_domain_consistency",
}
_COLUMN_CONTRACT = {
    "id": (False, "uuid", None),
    "resource_kind": (False, "string", None),
    "resource_key": (False, "string", None),
    "mode": (False, "string", "block"),
    "scope": (False, "string", "global"),
    "domain_id": (True, "uuid", None),
    "created_by": (True, "uuid", None),
    "created_at": (False, "datetime", "timestamp"),
    "updated_at": (False, "datetime", "timestamp"),
}


def _normalized_sql(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum() or character == "_")


def _matches_column_type(column_type: sa.types.TypeEngine, expected: str) -> bool:
    if expected == "string":
        return isinstance(column_type, sa.String)
    if expected == "datetime":
        return isinstance(column_type, sa.DateTime)
    if expected == "uuid":
        # SQLite reflects SQLAlchemy Uuid as CHAR(32); PostgreSQL reflects UUID.
        return isinstance(column_type, sa.Uuid) or (
            isinstance(column_type, sa.CHAR) and getattr(column_type, "length", None) == _SQLITE_UUID_LENGTH
        )
    return False


def _validate_columns(columns: list[dict[str, object]]) -> None:
    by_name = {str(column["name"]): column for column in columns}
    for column_name, (nullable, type_name, default_kind) in _COLUMN_CONTRACT.items():
        column = by_name[column_name]
        if bool(column["nullable"]) is not nullable:
            msg = f"{TABLE_NAME}.{column_name} has incorrect nullability"
            raise RuntimeError(msg)
        if not _matches_column_type(column["type"], type_name):
            msg = f"{TABLE_NAME}.{column_name} has an incompatible type"
            raise RuntimeError(msg)

        default = column.get("default")
        normalized_default = _normalized_sql(default) if default is not None else ""
        if default_kind is None and default is not None:
            msg = f"{TABLE_NAME}.{column_name} has an unexpected server default"
            raise RuntimeError(msg)
        if default_kind in {"block", "global", "timestamp"} and not normalized_default:
            msg = f"{TABLE_NAME}.{column_name} is missing its required server default"
            raise RuntimeError(msg)


def _validate_existing_table(conn: sa.Connection) -> None:
    """Fail loudly when a partial pre-existing table cannot be repaired safely."""
    inspector = sa.inspect(conn)
    reflected_columns = inspector.get_columns(TABLE_NAME)
    columns = {column["name"] for column in reflected_columns}
    missing_columns = _REQUIRED_COLUMNS - columns
    if missing_columns:
        msg = f"{TABLE_NAME} exists but is missing required columns: {sorted(missing_columns)}"
        raise RuntimeError(msg)
    _validate_columns(reflected_columns)

    reflected_checks = inspector.get_check_constraints(TABLE_NAME)
    checks = {constraint["name"] for constraint in reflected_checks}
    missing_checks = _REQUIRED_CHECKS - checks
    if missing_checks:
        msg = f"{TABLE_NAME} exists but is missing required check constraints: {sorted(missing_checks)}"
        raise RuntimeError(msg)
    primary_key = inspector.get_pk_constraint(TABLE_NAME)
    if primary_key.get("constrained_columns") != ["id"]:
        msg = f"{TABLE_NAME} exists without the required primary key on id"
        raise RuntimeError(msg)

    creator_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys(TABLE_NAME)
            if foreign_key.get("constrained_columns") == ["created_by"]
            and foreign_key.get("referred_table") == "user"
            and foreign_key.get("referred_columns") == ["id"]
        ),
        None,
    )
    ondelete = (creator_foreign_key or {}).get("options", {}).get("ondelete")
    if creator_foreign_key is None or str(ondelete).upper() != "SET NULL":
        msg = f"{TABLE_NAME} exists without the required created_by foreign key"
        raise RuntimeError(msg)


def _create_missing_indexes(conn: sa.Connection) -> None:
    """Create the NULL-safe uniqueness indexes when their columns exist."""
    if not all(migration.column_exists(TABLE_NAME, column_name, conn) for column_name in _REQUIRED_INDEX_COLUMNS):
        msg = f"{TABLE_NAME} is missing columns required by its unique indexes"
        raise RuntimeError(msg)

    indexes = {index["name"]: index for index in sa.inspect(conn).get_indexes(TABLE_NAME)}
    expected_indexes = {
        SCOPED_INDEX: ["resource_kind", "resource_key", "scope", "domain_id"],
        UNSCOPED_INDEX: ["resource_kind", "resource_key", "scope"],
    }
    for index_name, expected_columns in expected_indexes.items():
        index = indexes.get(index_name)
        if index is None:
            continue
        dialect_options = index.get("dialect_options") or {}
        predicate = dialect_options.get("sqlite_where")
        if predicate is None:
            predicate = dialect_options.get("postgresql_where")
        if index.get("column_names") != expected_columns or not bool(index.get("unique")) or predicate is None:
            msg = f"{TABLE_NAME}.{index_name} has an incompatible definition"
            raise RuntimeError(msg)

    existing_indexes = set(indexes)
    if SCOPED_INDEX not in existing_indexes:
        op.create_index(
            SCOPED_INDEX,
            TABLE_NAME,
            ["resource_kind", "resource_key", "scope", "domain_id"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NOT NULL"),
            sqlite_where=sa.text("domain_id IS NOT NULL"),
        )
    if UNSCOPED_INDEX not in existing_indexes:
        op.create_index(
            UNSCOPED_INDEX,
            TABLE_NAME,
            ["resource_kind", "resource_key", "scope"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NULL"),
            sqlite_where=sa.text("domain_id IS NULL"),
        )


def _insert_probe(conn: sa.Connection, **overrides: object) -> None:
    values = {
        "id": uuid4().hex,
        "resource_kind": "component",
        "resource_key": f"__catalog_policy_migration_probe_{uuid4().hex}",
        **overrides,
    }
    columns = list(values)
    column_sql = ", ".join(columns)
    value_sql = ", ".join(f":{column}" for column in columns)
    conn.execute(
        sa.text(f"INSERT INTO {TABLE_NAME} ({column_sql}) VALUES ({value_sql})"),  # noqa: S608
        values,
    )


def _expect_probe_rejected(conn: sa.Connection, *, reason: str, **overrides: object) -> None:
    savepoint = conn.begin_nested()
    try:
        _insert_probe(conn, **overrides)
    except sa.exc.IntegrityError:
        savepoint.rollback()
        return
    except Exception:
        savepoint.rollback()
        raise
    savepoint.rollback()
    msg = f"{TABLE_NAME} failed to enforce {reason}"
    raise RuntimeError(msg)


def _expect_probe_accepted(conn: sa.Connection, *, reason: str, **overrides: object) -> None:
    savepoint = conn.begin_nested()
    try:
        _insert_probe(conn, **overrides)
    except sa.exc.IntegrityError as exc:
        savepoint.rollback()
        msg = f"{TABLE_NAME} rejects {reason}"
        raise RuntimeError(msg) from exc
    except Exception:
        savepoint.rollback()
        raise
    savepoint.commit()


def _validate_table_behavior(conn: sa.Connection) -> None:
    """Probe defaults and constraints inside a rolled-back savepoint."""
    savepoint = conn.begin_nested()
    global_key = f"__catalog_policy_global_probe_{uuid4().hex}"
    try:
        _insert_probe(conn, resource_key=global_key)
        stored = conn.execute(
            sa.text(
                """
                SELECT mode, scope, domain_id, created_at, updated_at
                FROM catalog_policy_rule
                WHERE resource_key = :resource_key
                """
            ),
            {"resource_key": global_key},
        ).one()
        if (
            stored.mode != "block"
            or stored.scope != "global"
            or stored.domain_id is not None
            or stored.created_at is None
            or stored.updated_at is None
        ):
            msg = f"{TABLE_NAME} has incompatible default values"
            raise RuntimeError(msg)

        _expect_probe_rejected(
            conn,
            reason="global NULL-safe uniqueness",
            resource_key=global_key,
        )
        _expect_probe_rejected(conn, reason="resource-kind checks", resource_kind="flow")
        _expect_probe_rejected(conn, reason="mode checks", mode="deny")
        _expect_probe_rejected(conn, reason="scope checks", scope="tenant")
        _expect_probe_rejected(
            conn,
            reason="global scope/domain consistency",
            domain_id=uuid4().hex,
        )
        _expect_probe_rejected(
            conn,
            reason="scoped scope/domain consistency",
            scope="workspace",
        )

        _expect_probe_accepted(conn, reason="valid template rules", resource_kind="template")
        _expect_probe_accepted(conn, reason="reserved allow-mode rules", mode="allow")
        _expect_probe_accepted(conn, reason="valid organization scopes", scope="org", domain_id=uuid4().hex)

        scoped_key = f"__catalog_policy_scoped_probe_{uuid4().hex}"
        scoped_domain = uuid4().hex
        _expect_probe_accepted(
            conn,
            reason="valid workspace scopes",
            resource_key=scoped_key,
            scope="workspace",
            domain_id=scoped_domain,
        )
        _expect_probe_accepted(
            conn,
            reason="the same key in distinct workspace domains",
            resource_key=scoped_key,
            scope="workspace",
            domain_id=uuid4().hex,
        )
        _expect_probe_rejected(
            conn,
            reason="scoped uniqueness",
            resource_key=scoped_key,
            scope="workspace",
            domain_id=scoped_domain,
        )
    finally:
        savepoint.rollback()


def upgrade() -> None:
    conn = op.get_bind()

    table_already_exists = migration.table_exists(TABLE_NAME, conn)
    if table_already_exists:
        _validate_existing_table(conn)
    else:
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("resource_kind", AutoString(), nullable=False),
            sa.Column("resource_key", AutoString(), nullable=False),
            sa.Column("mode", AutoString(), nullable=False, server_default=sa.text("'block'")),
            sa.Column("scope", AutoString(), nullable=False, server_default=sa.text("'global'")),
            sa.Column("domain_id", sa.Uuid(), nullable=True),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "resource_kind IN ('component', 'template')",
                name="ck_catalog_policy_rule_resource_kind",
            ),
            sa.CheckConstraint(
                "mode IN ('block', 'allow')",
                name="ck_catalog_policy_rule_mode",
            ),
            sa.CheckConstraint(
                "scope IN ('global', 'org', 'workspace')",
                name="ck_catalog_policy_rule_scope",
            ),
            sa.CheckConstraint(
                "(scope = 'global' AND domain_id IS NULL) OR (scope IN ('org', 'workspace') AND domain_id IS NOT NULL)",
                name="ck_catalog_policy_rule_scope_domain_consistency",
            ),
        )

    _create_missing_indexes(conn)
    if table_already_exists:
        _validate_table_behavior(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        op.drop_table(TABLE_NAME)
