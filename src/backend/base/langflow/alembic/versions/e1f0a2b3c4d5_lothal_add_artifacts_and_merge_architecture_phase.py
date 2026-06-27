"""lothal: add artifacts file-map column + remap diagram phases to ARCHITECTURE (E.1)

Revision ID: e1f0a2b3c4d5
Revises: a8f3c2e91d05
Create Date: 2026-06-27 00:00:00.000000

Phase: EXPAND

Epic E reframes the lifecycle so the two diagram phases collapse into a single
``ARCHITECTURE`` stage whose output is an ADR plus a set of D2 diagrams — a
variable-length artifact set, not one diagram. This migration lays the schema
groundwork:

1. **Add ``lothal_project.artifacts``** — a single nullable JSON column holding a
   generic ``{path: content}`` file-map (``{"adr.md": "...",
   "diagrams/context.d2": "...", ...}``). It is reused by every stage and is the
   future git commit tree verbatim. Nullable with no backfill: old projects keep
   rendering through ``diagram_d2``.

2. **Remap the phase data** — existing rows in the now-removed ``DIAGRAM_GENERATION``
   and ``DIAGRAM_REFINEMENT`` phases are moved to ``ARCHITECTURE`` in one UPDATE,
   so no live row holds a value the merged phase enum (Story E.2) no longer
   defines. ``phase`` is a plain string column (no DB-level enum/check
   constraint), so this is a pure data update.

Both run inside ``batch_alter_table`` / guarded statements so SQLite (the test DB)
and Postgres apply cleanly, and re-runs / a missing table are no-ops.

Downgrade drops the ``artifacts`` column. The phase remap is **not** reversed: the
two source phases collapse to one value, so the original
``DIAGRAM_GENERATION`` vs ``DIAGRAM_REFINEMENT`` distinction is unrecoverable —
re-splitting would have to guess and could mislabel rows. Leaving the data on
``ARCHITECTURE`` is the safe, honest choice (mirrors the D.13 backfill downgrade).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e1f0a2b3c4d5"
down_revision: str | None = "a8f3c2e91d05"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The diagram phases merged into ARCHITECTURE by Epic E.
_MERGED_PHASE = "ARCHITECTURE"
_OLD_DIAGRAM_PHASES = ("DIAGRAM_GENERATION", "DIAGRAM_REFINEMENT")


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    # 1. Add the generic artifact file-map column (nullable, no default, no backfill).
    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        if not migration.column_exists("lothal_project", "artifacts", conn):
            batch_op.add_column(sa.Column("artifacts", sa.JSON(), nullable=True))

    # 2. Remap any existing rows on the old diagram phases to the merged stage.
    #    Idempotent: rows already on ARCHITECTURE are untouched by the WHERE clause.
    lothal_project = sa.table(
        "lothal_project",
        sa.column("phase", sa.String()),
    )
    conn.execute(
        sa.update(lothal_project).where(lothal_project.c.phase.in_(_OLD_DIAGRAM_PHASES)).values(phase=_MERGED_PHASE)
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    # Drop the artifacts column. The phase remap is intentionally not reversed —
    # see the module docstring (the source phases are no longer distinguishable).
    with op.batch_alter_table("lothal_project", schema=None) as batch_op:
        if migration.column_exists("lothal_project", "artifacts", conn):
            batch_op.drop_column("artifacts")
