"""lothal: drop Mermaid storage, collapse to a single diagram_json column

Revision ID: a6ba6bdf00b7
Revises: f2e57d2327a2
Create Date: 2026-06-16 22:30:00.000000

Phase: EXPAND

Lothal goes xyflow-only (no Mermaid). The two diagram columns collapse into one:
drop ``lothal_project.diagram_mmd`` (the canonical Mermaid text) and rename
``diagram_layout`` (xyflow positions) to ``diagram_json``, which now holds the
full xyflow graph (nodes-with-positions + edges) as a JSON string — the single
diagram source of truth. Pre-prod / dev-only data, so the destructive drop is
acceptable; both columns are nullable Text, so the rename is type-preserving.

All column work runs inside ``batch_alter_table`` so SQLite (the test DB) can
drop/rename via its table-rebuild path, and so Postgres applies a plain ALTER.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a6ba6bdf00b7"
down_revision: str | None = "f2e57d2327a2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        if migration.column_exists("lothal_project", "diagram_mmd", conn):
            batch_op.drop_column("diagram_mmd")
        if migration.column_exists("lothal_project", "diagram_layout", conn) and not migration.column_exists(
            "lothal_project", "diagram_json", conn
        ):
            batch_op.alter_column(
                "diagram_layout",
                new_column_name="diagram_json",
                existing_type=sa.Text(),
                existing_nullable=True,
            )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        if migration.column_exists("lothal_project", "diagram_json", conn) and not migration.column_exists(
            "lothal_project", "diagram_layout", conn
        ):
            batch_op.alter_column(
                "diagram_json",
                new_column_name="diagram_layout",
                existing_type=sa.Text(),
                existing_nullable=True,
            )
        if not migration.column_exists("lothal_project", "diagram_mmd", conn):
            batch_op.add_column(sa.Column("diagram_mmd", sa.Text(), nullable=True))
