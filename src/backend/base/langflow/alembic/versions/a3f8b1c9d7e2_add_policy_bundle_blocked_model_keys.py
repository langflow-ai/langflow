"""Add blocked model keys to policy bundle revisions.

Phase: EXPAND
Revision ID: a3f8b1c9d7e2
Revises: f7a9c2d4e6b8
Create Date: 2026-08-11 00:00:00.000000

Revisions written before this migration carry no model blocks; the nullable
column with a server default lets them read back as an empty deny-list
without a backfill, and their stored content hashes remain valid because the
canonical hash payload includes ``blocked_model_keys`` only when the set is
non-empty. Writers always provide the value, so a follow-up CONTRACT phase
may tighten the column to NOT NULL once no pre-expand release remains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a3f8b1c9d7e2"  # pragma: allowlist secret
down_revision: str | None = "f7a9c2d4e6b8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_TABLE = "policy_bundle_revision"
COLUMN_NAME = "blocked_model_keys"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(REVISION_TABLE, conn):
        return
    if not migration.column_exists(REVISION_TABLE, COLUMN_NAME, conn):
        op.add_column(
            REVISION_TABLE,
            sa.Column(COLUMN_NAME, sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(REVISION_TABLE, conn):
        return
    if migration.column_exists(REVISION_TABLE, COLUMN_NAME, conn):
        with op.batch_alter_table(REVISION_TABLE) as batch_op:
            batch_op.drop_column(COLUMN_NAME)
