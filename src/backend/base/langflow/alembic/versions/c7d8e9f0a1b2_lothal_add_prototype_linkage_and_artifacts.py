"""lothal: add prototype linkage columns + prototype-artifact table (Epic UI, Story U.1)

Revision ID: c7d8e9f0a1b2
Revises: e1f0a2b3c4d5
Create Date: 2026-06-28 00:00:00.000000

Phase: EXPAND

Epic UI inserts a PROTOTYPE stage in which Lothal drives Open Design (OD) as a
headless prototyping engine. Story U.1 lays the persistence groundwork:

1. **``lothal_project`` linkage + status columns** —
   ``od_project_id`` / ``od_conversation_id`` reference the OD project and
   conversation Lothal seeds (nullable; populated when the stage starts).
   ``prototype_status`` tracks the run lifecycle (``IDLE → GENERATING → READY →
   APPROVED``): NOT NULL with a server default of ``IDLE`` so existing rows get a
   well-defined value. ``prototype_approved_at`` records the approval boundary at
   which finalised artifacts are copied in (nullable).

2. **``lothal_prototype_artifact``** — one row per retained prototype artifact
   (DB-as-source-of-truth: copied on approve). FK to ``lothal_project`` with
   ``ondelete=CASCADE``, matching the other lothal tables (f2e57d2327a2).

Every statement is guarded (table/column existence) and wrapped in
``batch_alter_table`` so it applies cleanly on both SQLite (the test DB) and
Postgres, on a fresh as well as an existing database, and re-runs as a no-op.

Downgrade drops the artifact table and the four columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "e1f0a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_COLUMNS = (
    ("od_project_id", sa.Text()),
    ("od_conversation_id", sa.Text()),
    ("prototype_approved_at", sa.DateTime()),
)


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    # 1. Prototype linkage / status columns on lothal_project.
    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        for name, col_type in _NEW_COLUMNS:
            if not migration.column_exists("lothal_project", name, conn):
                batch_op.add_column(sa.Column(name, col_type, nullable=True))
        if not migration.column_exists("lothal_project", "prototype_status", conn):
            batch_op.add_column(
                sa.Column("prototype_status", sa.Text(), nullable=False, server_default="IDLE"),
            )

    # 2. Retained-artifact table (one row per copied OD artifact).
    if not migration.table_exists("lothal_prototype_artifact", conn):
        op.create_table(
            "lothal_prototype_artifact",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("od_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("manifest", sa.JSON(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["lothal_project.id"],
                name="fk_lothal_prototype_artifact_project_id_lothal_project",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("lothal_prototype_artifact", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_lothal_prototype_artifact_project_id"), ["project_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    if migration.table_exists("lothal_prototype_artifact", conn):
        with op.batch_alter_table("lothal_prototype_artifact", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_lothal_prototype_artifact_project_id"))
        op.drop_table("lothal_prototype_artifact")

    if not migration.table_exists("lothal_project", conn):
        return

    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        for name in ("prototype_status", "prototype_approved_at", "od_conversation_id", "od_project_id"):
            if migration.column_exists("lothal_project", name, conn):
                batch_op.drop_column(name)
