"""lothal: add diagram_d2 column (D2 source becomes the diagram artifact)

Revision ID: 66bb47eb00f6
Revises: a6ba6bdf00b7
Create Date: 2026-06-18 00:00:00.000000

Phase: EXPAND

Epic D pivots the diagram surface from an xyflow graph (``diagram_json``) to D2
source. Add a nullable ``lothal_project.diagram_d2`` TEXT column to hold the D2
text. ``diagram_json`` is intentionally left in place for existing data and the
transitional read path; its removal is a later, separate migration (D.13).

The add runs inside ``batch_alter_table`` so SQLite (the test DB) and Postgres
both apply cleanly, and is guarded so re-runs / a missing table are no-ops.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "66bb47eb00f6"
down_revision: str | None = "a6ba6bdf00b7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        if not migration.column_exists("lothal_project", "diagram_d2", conn):
            batch_op.add_column(sa.Column("diagram_d2", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        if migration.column_exists("lothal_project", "diagram_d2", conn):
            batch_op.drop_column("diagram_d2")
