"""add flow version token and last modified by

Revision ID: 439697865628
Revises: c6d8e0f2a4b7
Create Date: 2026-09-02 07:44:12.238816

Phase: EXPAND
Safe to rollback: YES (two nullable columns and one index, no backfill).
Services compatible: All versions. Older services never read either column;
    newer ones treat NULL as "row predates preconditions", which is the same
    behaviour they give an unconditional write, so an in-flight client cannot
    break across the upgrade.

``version_token`` is rotated whenever a flow's ``data`` changes, and a client
sends the token it read back as a save precondition. ``last_modified_by``
records who performed that change so a refused save can name them. It is
deliberately not a foreign key: ``user_id`` already links these tables, and a
second path makes the ``Flow.user`` relationship ambiguous to SQLAlchemy.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "439697865628"  # pragma: allowlist secret
down_revision: str | None = "c6d8e0f2a4b7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if not migration.column_exists(table_name="flow", column_name="version_token", conn=conn):
            batch_op.add_column(sa.Column("version_token", sa.Uuid(), nullable=True))
        if not migration.column_exists(table_name="flow", column_name="last_modified_by", conn=conn):
            batch_op.add_column(sa.Column("last_modified_by", sa.Uuid(), nullable=True))
            batch_op.create_index(batch_op.f("ix_flow_last_modified_by"), ["last_modified_by"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("flow", schema=None) as batch_op:
        if migration.column_exists(table_name="flow", column_name="last_modified_by", conn=conn):
            batch_op.drop_index(batch_op.f("ix_flow_last_modified_by"))
            batch_op.drop_column("last_modified_by")
        if migration.column_exists(table_name="flow", column_name="version_token", conn=conn):
            batch_op.drop_column("version_token")
