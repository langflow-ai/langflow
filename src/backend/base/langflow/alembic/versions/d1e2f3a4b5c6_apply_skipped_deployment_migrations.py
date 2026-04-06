"""apply_skipped_deployment_migrations

Phase: EXPAND

Applies schema changes from c0d2ce43b315 that were bypassed on DBs
that migrated via the old memory_base chain:

  - deployment.description (Text, nullable)
  - deployment.deployment_type (Enum, nullable) — added directly as enum
    because a1b2c3d4e5f6 (convert-to-enum) already ran as a no-op
  - flow_version_deployment_attachment table + indexes

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-04-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "flow_version_deployment_attachment"
DEPLOYMENT_TABLE = "deployment"


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  deployment columns  (from c0d2ce43b315 + a1b2c3d4e5f6 convert)     #
    # ------------------------------------------------------------------ #
    deployment_type_enum = sa.Enum("agent", name="deployment_type_enum")
    deployment_type_enum.create(conn, checkfirst=True)

    if not migration.column_exists(DEPLOYMENT_TABLE, "deployment_type", conn):
        op.add_column(DEPLOYMENT_TABLE, sa.Column("deployment_type", deployment_type_enum, nullable=True))
        op.create_index("ix_deployment_deployment_type", DEPLOYMENT_TABLE, ["deployment_type"])

    if not migration.column_exists(DEPLOYMENT_TABLE, "description", conn):
        op.add_column(DEPLOYMENT_TABLE, sa.Column("description", sa.Text(), nullable=True))

    # ------------------------------------------------------------------ #
    #  flow_version_deployment_attachment  (from c0d2ce43b315)             #
    # ------------------------------------------------------------------ #
    if not migration.table_exists(TABLE_NAME, conn):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("flow_version_id", sa.Uuid(), nullable=False),
            sa.Column("deployment_id", sa.Uuid(), nullable=False),
            sa.Column("provider_snapshot_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["flow_version_id"], ["flow_version.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["deployment_id"], ["deployment.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_version_id", "deployment_id", name="uq_flow_version_deployment"),
        )
        op.create_index(op.f("ix_flow_version_deployment_attachment_user_id"), TABLE_NAME, ["user_id"])
        op.create_index(op.f("ix_flow_version_deployment_attachment_flow_version_id"), TABLE_NAME, ["flow_version_id"])
        op.create_index(op.f("ix_flow_version_deployment_attachment_deployment_id"), TABLE_NAME, ["deployment_id"])
        op.create_index(
            op.f("ix_flow_version_deployment_attachment_provider_snapshot_id"), TABLE_NAME, ["provider_snapshot_id"]
        )


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists(TABLE_NAME, conn):
        op.drop_index(op.f("ix_flow_version_deployment_attachment_provider_snapshot_id"), table_name=TABLE_NAME)
        op.drop_index(op.f("ix_flow_version_deployment_attachment_deployment_id"), table_name=TABLE_NAME)
        op.drop_index(op.f("ix_flow_version_deployment_attachment_flow_version_id"), table_name=TABLE_NAME)
        op.drop_index(op.f("ix_flow_version_deployment_attachment_user_id"), table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)

    if migration.column_exists(DEPLOYMENT_TABLE, "description", conn):
        with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
            batch_op.drop_column("description")

    if migration.column_exists(DEPLOYMENT_TABLE, "deployment_type", conn):
        op.drop_index("ix_deployment_deployment_type", table_name=DEPLOYMENT_TABLE)
        with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
            batch_op.drop_column("deployment_type")

    sa.Enum("agent", name="deployment_type_enum").drop(conn, checkfirst=True)
