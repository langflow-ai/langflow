"""add flow operation history

Revision ID: e3a7b9c1d5f2
Revises: d4f1a6c8e2b7
Create Date: 2026-09-28

Phase: EXPAND
Safe to rollback: YES. Downgrade drops recorded history and the system
    checkpoints that anchor it; saved flow versions and flow data are kept.
Services compatible: All versions. Older services never read the new columns
    or table; flow.latest_revision and flow.current_revision default to 0, which
    newer services read as "no history yet" and start history from.

Adds the operation history of flow graphs:

- ``flow.latest_revision`` / ``flow.current_revision``: the highest recorded
  operation revision, and the revision ``flow.data`` holds;
- ``flow_operation``: append-only rows of ordered, attributed operations, each
  row covering a contiguous revision range, with database triggers refusing
  updates and deletes of rows whose flow still exists;
- ``flow_version`` checkpoint metadata: the revision a version's graph belongs
  to and its canonical hash, a ``view_only`` flag for the kept original of a
  repaired flow, and a nullable ``version_number`` for system checkpoints,
  which are not versions anyone saved.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.services.database.models.flow_operation import append_only
from langflow.utils import migration
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e3a7b9c1d5f2"  # pragma: allowlist secret
down_revision: str | None = "d4f1a6c8e2b7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVISION_ORDER_CHECK = "ck_flow_current_revision_not_ahead"
_REVISION_RANGE_CHECK = "ck_flow_operation_revision_range"
_CHECKPOINT_INDEX = "ix_flow_version_flow_id_operation_revision"
_LOOKUP_INDEXES = {
    "ix_flow_operation_actor_user_ids": "actor_user_ids",
    "ix_flow_operation_request_ids": "request_ids",
}


def _check_names(conn: sa.Connection, table: str) -> set[str]:
    return {check["name"] for check in sa.inspect(conn).get_check_constraints(table)}


def _index_names(conn: sa.Connection, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(conn).get_indexes(table)}


def _upgrade_flow(conn: sa.Connection) -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow", column_name="latest_revision", conn=conn):
            batch_op.add_column(
                sa.Column("latest_revision", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
            )
        if not migration.column_exists(table_name="flow", column_name="current_revision", conn=conn):
            batch_op.add_column(
                sa.Column("current_revision", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
            )

    if _REVISION_ORDER_CHECK in _check_names(conn, "flow"):
        return
    condition = "current_revision <= latest_revision"
    if conn.dialect.name == "sqlite":
        # SQLite cannot add a CHECK in place; the batch rebuild copies the table.
        with op.batch_alter_table("flow", recreate="always") as batch_op:
            batch_op.create_check_constraint(op.f(_REVISION_ORDER_CHECK), condition)
    else:
        op.create_check_constraint(op.f(_REVISION_ORDER_CHECK), "flow", condition)


def _upgrade_flow_version(conn: sa.Connection) -> None:
    with op.batch_alter_table("flow_version", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow_version", column_name="operation_revision", conn=conn):
            batch_op.add_column(sa.Column("operation_revision", sa.BigInteger(), nullable=True))
        if not migration.column_exists(table_name="flow_version", column_name="graph_hash", conn=conn):
            batch_op.add_column(sa.Column("graph_hash", sa.String(length=64), nullable=True))
        if not migration.column_exists(table_name="flow_version", column_name="view_only", conn=conn):
            batch_op.add_column(sa.Column("view_only", sa.Boolean(), nullable=False, server_default=sa.false()))

    version_number = next(
        column for column in sa.inspect(conn).get_columns("flow_version") if column["name"] == "version_number"
    )
    if not version_number["nullable"]:
        with op.batch_alter_table("flow_version", schema=None) as batch_op:
            batch_op.alter_column("version_number", existing_type=sa.Integer(), nullable=True)

    if _CHECKPOINT_INDEX not in _index_names(conn, "flow_version"):
        op.create_index(_CHECKPOINT_INDEX, "flow_version", ["flow_id", "operation_revision"])


def _create_flow_operation(conn: sa.Connection) -> None:
    lookup_list = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    if not migration.table_exists("flow_operation", conn):
        op.create_table(
            "flow_operation",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("start_revision", sa.BigInteger(), nullable=False),
            sa.Column("end_revision", sa.BigInteger(), nullable=False),
            sa.Column("ops", sa.JSON(), nullable=False),
            sa.Column("actor_user_ids", lookup_list, nullable=False),
            sa.Column("request_ids", lookup_list, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("start_revision <= end_revision", name=op.f(_REVISION_RANGE_CHECK)),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_id", "start_revision", name="uq_flow_operation_flow_id_start_revision"),
            sa.UniqueConstraint("flow_id", "end_revision", name="uq_flow_operation_flow_id_end_revision"),
        )

    if conn.dialect.name == "postgresql":
        existing = _index_names(conn, "flow_operation")
        for index_name, column in _LOOKUP_INDEXES.items():
            if index_name not in existing:
                op.create_index(
                    index_name,
                    "flow_operation",
                    [column],
                    postgresql_using="gin",
                    postgresql_ops={column: "jsonb_path_ops"},
                )

    for statement in append_only.create_statements(conn.dialect.name):
        op.execute(sa.text(statement))


def upgrade() -> None:
    conn = op.get_bind()
    _upgrade_flow(conn)
    _upgrade_flow_version(conn)
    _create_flow_operation(conn)


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("flow_operation", conn):
        for statement in append_only.drop_statements(conn.dialect.name):
            op.execute(sa.text(statement))
        op.drop_table("flow_operation")

    # System checkpoints have no version number; they anchor the history just
    # dropped and mean nothing without it.
    if migration.column_exists(table_name="flow_version", column_name="operation_revision", conn=conn):
        conn.execute(sa.text("DELETE FROM flow_version WHERE version_number IS NULL"))
    if _CHECKPOINT_INDEX in _index_names(conn, "flow_version"):
        op.drop_index(_CHECKPOINT_INDEX, table_name="flow_version")
    with op.batch_alter_table("flow_version", schema=None) as batch_op:
        for column in ("view_only", "graph_hash", "operation_revision"):
            if migration.column_exists(table_name="flow_version", column_name=column, conn=conn):
                batch_op.drop_column(column)
        batch_op.alter_column("version_number", existing_type=sa.Integer(), nullable=False)

    if _REVISION_ORDER_CHECK in _check_names(conn, "flow"):
        if conn.dialect.name == "sqlite":
            with op.batch_alter_table("flow", recreate="always") as batch_op:
                batch_op.drop_constraint(op.f(_REVISION_ORDER_CHECK), type_="check")
        else:
            op.drop_constraint(op.f(_REVISION_ORDER_CHECK), "flow", type_="check")
    with op.batch_alter_table("flow", schema=None) as batch_op:
        for column in ("current_revision", "latest_revision"):
            if migration.column_exists(table_name="flow", column_name=column, conn=conn):
                batch_op.drop_column(column)
