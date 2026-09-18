"""Add the native team-sharing and optimistic-write contract.

Revision ID: bf6c22022777
Revises: c6d8e0f2a4b7
Create Date: 2026-09-03

Phase: MIGRATE

Existing rows receive deterministic scalar values only. Existing inactive
teams are marked ``manual``; no member is promoted to Team Admin because the
correct administrator cannot be inferred safely. Operators must use the
explicit team preflight/repair command before enabling collaboration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlmodel.sql.sqltypes import AutoString

revision: str = "bf6c22022777"  # pragma: allowlist secret
down_revision: str | None = "c6d8e0f2a4b7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEAM = "authz_team"
_MEMBER = "authz_team_member"
_SHARE = "authz_share"


def _index_exists(conn: sa.Connection, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in sa.inspect(conn).get_indexes(table_name))


def _check_actual_name(conn: sa.Connection, table_name: str, check_name: str) -> str | None:
    """Resolve naming-convention-prefixed check names on every dialect."""
    for check in sa.inspect(conn).get_check_constraints(table_name):
        actual = check["name"]
        if actual == check_name or (actual is not None and actual.endswith(f"_{check_name}")):
            return actual
    return None


def _check_exists(conn: sa.Connection, table_name: str, check_name: str) -> bool:
    return _check_actual_name(conn, table_name, check_name) is not None


def _add_columns(conn: sa.Connection) -> None:
    if migration.table_exists(_TEAM, conn) and not migration.column_exists(_TEAM, "inactivation_reason", conn):
        with op.batch_alter_table(_TEAM, schema=None) as batch_op:
            batch_op.add_column(sa.Column("inactivation_reason", AutoString(), nullable=True))

    if migration.table_exists(_MEMBER, conn):
        with op.batch_alter_table(_MEMBER, schema=None) as batch_op:
            if not migration.column_exists(_MEMBER, "role", conn):
                batch_op.add_column(
                    sa.Column(
                        "role",
                        AutoString(),
                        nullable=False,
                        server_default=sa.text("'user'"),
                    )
                )
            if not migration.column_exists(_MEMBER, "updated_at", conn):
                batch_op.add_column(
                    sa.Column(
                        "updated_at",
                        sa.DateTime(timezone=True),
                        nullable=False,
                        server_default=sa.func.now(),
                    )
                )

    if migration.table_exists(_SHARE, conn):
        with op.batch_alter_table(_SHARE, schema=None) as batch_op:
            if not migration.column_exists(_SHARE, "revision", conn):
                batch_op.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")))
            if not migration.column_exists(_SHARE, "updated_at", conn):
                batch_op.add_column(
                    sa.Column(
                        "updated_at",
                        sa.DateTime(timezone=True),
                        nullable=False,
                        server_default=sa.func.now(),
                    )
                )

    for table_name in ("flow", "folder"):
        if migration.table_exists(table_name, conn) and not migration.column_exists(table_name, "edit_revision", conn):
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column("edit_revision", sa.Integer(), nullable=False, server_default=sa.text("1"))
                )


def _backfill(conn: sa.Connection) -> None:
    if migration.table_exists(_TEAM, conn):
        conn.execute(
            sa.text(
                "UPDATE authz_team SET inactivation_reason = 'manual' "
                "WHERE is_active = false AND inactivation_reason IS NULL"
            )
        )
        conn.execute(sa.text("UPDATE authz_team SET inactivation_reason = NULL WHERE is_active = true"))


def _add_constraints_and_indexes(conn: sa.Connection) -> None:
    if migration.table_exists(_TEAM, conn) and not _check_exists(conn, _TEAM, "ck_authz_team_inactivation_reason"):
        with op.batch_alter_table(_TEAM, schema=None) as batch_op:
            batch_op.create_check_constraint(
                "ck_authz_team_inactivation_reason",
                "(is_active AND inactivation_reason IS NULL) OR "
                "(NOT is_active AND inactivation_reason IN ('manual', 'no_active_admin'))",
            )

    if migration.table_exists(_MEMBER, conn):
        if not _check_exists(conn, _MEMBER, "ck_authz_team_member_role"):
            with op.batch_alter_table(_MEMBER, schema=None) as batch_op:
                batch_op.create_check_constraint(
                    "ck_authz_team_member_role",
                    "role IN ('admin', 'maintainer', 'user')",
                )
        if not _index_exists(conn, _MEMBER, "ix_authz_team_member_team_role"):
            op.create_index(
                "ix_authz_team_member_team_role",
                _MEMBER,
                ["team_id", "role"],
                unique=False,
            )

    if migration.table_exists(_SHARE, conn) and not _check_exists(conn, _SHARE, "ck_authz_share_revision_positive"):
        with op.batch_alter_table(_SHARE, schema=None) as batch_op:
            batch_op.create_check_constraint(
                "ck_authz_share_revision_positive",
                "revision >= 1",
            )


def upgrade() -> None:
    conn = op.get_bind()
    _add_columns(conn)
    _backfill(conn)
    _add_constraints_and_indexes(conn)


def _drop_check_if_present(conn: sa.Connection, table_name: str, check_name: str) -> None:
    if not migration.table_exists(table_name, conn):
        return
    actual_name = _check_actual_name(conn, table_name, check_name)
    if actual_name is not None:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_constraint(op.f(actual_name), type_="check")


def downgrade() -> None:
    conn = op.get_bind()

    _drop_check_if_present(conn, _SHARE, "ck_authz_share_revision_positive")
    _drop_check_if_present(conn, _MEMBER, "ck_authz_team_member_role")
    _drop_check_if_present(conn, _TEAM, "ck_authz_team_inactivation_reason")

    if migration.table_exists(_MEMBER, conn) and _index_exists(conn, _MEMBER, "ix_authz_team_member_team_role"):
        op.drop_index("ix_authz_team_member_team_role", table_name=_MEMBER)

    for table_name, columns in (
        ("folder", ("edit_revision",)),
        ("flow", ("edit_revision",)),
        (_SHARE, ("updated_at", "revision")),
        (_MEMBER, ("updated_at", "role")),
        (_TEAM, ("inactivation_reason",)),
    ):
        if not migration.table_exists(table_name, conn):
            continue
        for column_name in columns:
            if migration.column_exists(table_name, column_name, conn):
                with op.batch_alter_table(table_name, schema=None) as batch_op:
                    batch_op.drop_column(column_name)
