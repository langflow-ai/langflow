"""hardening pass on authz schema (timestamps, indexes, FKs, partial-index gap)

Revision ID: f0a1b2c3d4e5
Revises: e4f5a6b7c8d9
Create Date: 2026-05-20

Phase: EXPAND

Five fixes against findings from the review of PR #13153:

1. ``casbin_rule.ptype`` had no index. Casbin's loader filters by ``ptype`` on
   every ``load_policy()`` / ``AddPolicy()``; the missing index turned every
   enterprise policy refresh into a full table scan.

2. Every authz timestamp column was created with ``sa.DateTime()`` (no tz),
   inconsistent with the rest of the project. On Postgres this strips
   ``tzinfo`` on write; Python writes UTC and reads naive, breaking
   audit-log ordering across DST and any cross-tz comparison. Switch to
   ``DateTime(timezone=True)`` and convert existing naive values assuming UTC
   (matches the application-side ``datetime.now(timezone.utc)`` default
   that produced them).

3. ``uq_authz_role_assignment_global`` filtered on
   ``domain_type = 'global' AND domain_id IS NULL`` — a row with
   ``domain_type='org' AND domain_id IS NULL`` was covered by neither partial
   index and duplicates slipped through. Widen the filter to ``domain_id IS
   NULL`` (rename the index to reflect that it is no longer global-only).

4. ``authz_share.created_by`` was ``ondelete='CASCADE'`` — deleting a user
   silently revoked every share they created. Mirror the ``SET NULL`` pattern
   already used by ``authz_audit_log.user_id``.

5. Hot-path query ``WHERE resource_type=$1 AND resource_id=$2`` on
   ``authz_share`` had no composite index. Add ``ix_authz_share_resource``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "f0a1b2c3d4e5"  # pragma: allowlist secret
down_revision: str | None = "e4f5a6b7c8d9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    return index_name in [ix["name"] for ix in inspector.get_indexes(table_name)]


# ((table, [columns_with_naive_DateTime]))
_TZ_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("authz_role", ("created_at", "updated_at")),
    ("authz_role_assignment", ("assigned_at",)),
    ("authz_team", ("created_at", "updated_at")),
    ("authz_team_member", ("created_at",)),
    ("authz_share", ("created_at",)),
    ("authz_edit_lock", ("acquired_at", "expires_at")),
    ("authz_audit_log", ("timestamp",)),
)


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # ---- 1. casbin_rule.ptype index -----------------------------------------
    if migration.table_exists("casbin_rule", conn) and not _index_exists(conn, "casbin_rule", "ix_casbin_rule_ptype"):
        op.create_index("ix_casbin_rule_ptype", "casbin_rule", ["ptype"])

    # ---- 2. DateTime → DateTime(timezone=True) ------------------------------
    # On Postgres, naive TIMESTAMP → TIMESTAMP WITH TIME ZONE needs a USING
    # clause to declare the assumed source zone. The app writes UTC, so
    # ``column AT TIME ZONE 'UTC'`` is the correct conversion.
    # On SQLite, batch_alter_table recreates the table; the text values are
    # preserved verbatim and the new column type is purely informational.
    for table_name, columns in _TZ_TABLES:
        if not migration.table_exists(table_name, conn):
            continue
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            for column in columns:
                kwargs: dict = {
                    "type_": sa.DateTime(timezone=True),
                    "existing_type": sa.DateTime(),
                    "existing_nullable": False,
                }
                if dialect == "postgresql":
                    kwargs["postgresql_using"] = f"{column} AT TIME ZONE 'UTC'"
                batch_op.alter_column(column, **kwargs)

    # ---- 3. widen role_assignment global partial index ----------------------
    if migration.table_exists("authz_role_assignment", conn):
        if _index_exists(conn, "authz_role_assignment", "uq_authz_role_assignment_global"):
            op.drop_index("uq_authz_role_assignment_global", table_name="authz_role_assignment")
        if not _index_exists(conn, "authz_role_assignment", "uq_authz_role_assignment_unscoped"):
            op.create_index(
                "uq_authz_role_assignment_unscoped",
                "authz_role_assignment",
                ["user_id", "role_id", "domain_type"],
                unique=True,
                postgresql_where=sa.text("domain_id IS NULL"),
                sqlite_where=sa.text("domain_id IS NULL"),
            )

    # ---- 4. authz_share.created_by → nullable + SET NULL --------------------
    # ``batch_alter_table`` rewrites the constraint set on SQLite; on Postgres
    # the FK has to be dropped and re-added because alter_column won't change
    # ondelete behavior.
    if migration.table_exists("authz_share", conn):
        with op.batch_alter_table("authz_share", schema=None) as batch_op:
            batch_op.alter_column(
                "created_by",
                existing_type=sa.Uuid(),
                nullable=True,
            )
            # Find the existing FK name (autogen-emitted) and replace it.
            inspector = sa.inspect(conn)
            for fk in inspector.get_foreign_keys("authz_share"):
                if fk.get("constrained_columns") == ["created_by"]:
                    batch_op.drop_constraint(fk["name"], type_="foreignkey")
                    break
            batch_op.create_foreign_key(
                "fk_authz_share_created_by_user",
                "user",
                ["created_by"],
                ["id"],
                ondelete="SET NULL",
            )

    # ---- 5. composite ix on authz_share -------------------------------------
    if migration.table_exists("authz_share", conn) and not _index_exists(
        conn, "authz_share", "ix_authz_share_resource"
    ):
        op.create_index(
            "ix_authz_share_resource",
            "authz_share",
            ["resource_type", "resource_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # ---- 5. composite ix on authz_share -------------------------------------
    if migration.table_exists("authz_share", conn) and _index_exists(conn, "authz_share", "ix_authz_share_resource"):
        op.drop_index("ix_authz_share_resource", table_name="authz_share")

    # ---- 4. revert authz_share.created_by FK + nullability ------------------
    if migration.table_exists("authz_share", conn):
        with op.batch_alter_table("authz_share", schema=None) as batch_op:
            inspector = sa.inspect(conn)
            for fk in inspector.get_foreign_keys("authz_share"):
                if fk.get("constrained_columns") == ["created_by"]:
                    batch_op.drop_constraint(fk["name"], type_="foreignkey")
                    break
            batch_op.create_foreign_key(
                "fk_authz_share_created_by_user",
                "user",
                ["created_by"],
                ["id"],
                ondelete="CASCADE",
            )
            batch_op.alter_column(
                "created_by",
                existing_type=sa.Uuid(),
                nullable=False,
            )

    # ---- 3. restore old role_assignment global partial index ----------------
    if migration.table_exists("authz_role_assignment", conn):
        if _index_exists(conn, "authz_role_assignment", "uq_authz_role_assignment_unscoped"):
            op.drop_index("uq_authz_role_assignment_unscoped", table_name="authz_role_assignment")
        if not _index_exists(conn, "authz_role_assignment", "uq_authz_role_assignment_global"):
            op.create_index(
                "uq_authz_role_assignment_global",
                "authz_role_assignment",
                ["user_id", "role_id", "domain_type"],
                unique=True,
                postgresql_where=sa.text("domain_type = 'global' AND domain_id IS NULL"),
                sqlite_where=sa.text("domain_type = 'global' AND domain_id IS NULL"),
            )

    # ---- 2. DateTime(timezone=True) → DateTime ------------------------------
    for table_name, columns in _TZ_TABLES:
        if not migration.table_exists(table_name, conn):
            continue
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            for column in columns:
                kwargs: dict = {
                    "type_": sa.DateTime(),
                    "existing_type": sa.DateTime(timezone=True),
                    "existing_nullable": False,
                }
                if dialect == "postgresql":
                    kwargs["postgresql_using"] = f"{column} AT TIME ZONE 'UTC'"
                batch_op.alter_column(column, **kwargs)

    # ---- 1. casbin_rule.ptype index -----------------------------------------
    if migration.table_exists("casbin_rule", conn) and _index_exists(conn, "casbin_rule", "ix_casbin_rule_ptype"):
        op.drop_index("ix_casbin_rule_ptype", table_name="casbin_rule")
