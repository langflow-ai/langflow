"""add flow version saved_by_user_id

Revision ID: f4b8c2d6e9a1
Revises: e3a7b9c1d5f2
Create Date: 2026-09-28

Phase: EXPAND
Safe to rollback: YES (one nullable column; downgrade drops it).
Services compatible: All versions. Older services never read the column.

``flow_version.user_id`` is the owner of the parent flow and scopes version
queries. Who saved a version is a separate fact: on a shared flow it need not
be the owner. The new ``saved_by_user_id`` records it, starting from the
existing ``user_id`` (every version saved so far was saved by its flow's
owner), and ``user_id`` is then aligned with the parent flow's owner so the two
meanings cannot drift.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "f4b8c2d6e9a1"  # pragma: allowlist secret
down_revision: str | None = "e3a7b9c1d5f2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_flow_version_saved_by_user_id"
_FOREIGN_KEY = "fk_flow_version_saved_by_user_id_user"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.column_exists(table_name="flow_version", column_name="saved_by_user_id", conn=conn):
        with op.batch_alter_table("flow_version", schema=None) as batch_op:
            batch_op.add_column(sa.Column("saved_by_user_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(_FOREIGN_KEY, "user", ["saved_by_user_id"], ["id"], ondelete="SET NULL")
            batch_op.create_index(_INDEX, ["saved_by_user_id"], unique=False)

        # System checkpoints have no author; every saved version so far was
        # saved by its flow's owner.
        conn.execute(
            sa.text(
                "UPDATE flow_version SET saved_by_user_id = user_id "
                "WHERE saved_by_user_id IS NULL AND version_number IS NOT NULL"
            )
        )
        conn.execute(
            sa.text(
                "UPDATE flow_version "
                "SET user_id = (SELECT flow.user_id FROM flow WHERE flow.id = flow_version.flow_id) "
                "WHERE EXISTS (SELECT 1 FROM flow WHERE flow.id = flow_version.flow_id)"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.column_exists(table_name="flow_version", column_name="saved_by_user_id", conn=conn):
        with op.batch_alter_table("flow_version", schema=None) as batch_op:
            batch_op.drop_index(_INDEX)
            batch_op.drop_constraint(_FOREIGN_KEY, type_="foreignkey")
            batch_op.drop_column("saved_by_user_id")
