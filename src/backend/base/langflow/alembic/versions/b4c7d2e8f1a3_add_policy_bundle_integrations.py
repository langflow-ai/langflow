"""Add integration governance to policy bundle revisions.

Phase: EXPAND
Revision ID: b4c7d2e8f1a3
Revises: a7d8e9f0b1c2
Create Date: 2026-09-05 00:00:00.000000

Revisions written before this migration govern no integrations; the two
nullable columns with server defaults let them read back as "unrestricted, and
nothing blocked" without a backfill, and their stored content hashes remain
valid because the canonical hash payload includes each integration field only
when its set is non-empty. Writers always provide both values, so a follow-up
CONTRACT phase may tighten the columns to NOT NULL once no pre-expand release
remains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b4c7d2e8f1a3"  # pragma: allowlist secret
down_revision: str | None = "a7d8e9f0b1c2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_TABLE = "policy_bundle_revision"
COLUMN_NAMES = ("approved_integration_provider_ids", "blocked_integration_action_keys")


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(REVISION_TABLE, conn):
        return
    for column_name in COLUMN_NAMES:
        if not migration.column_exists(REVISION_TABLE, column_name, conn):
            op.add_column(
                REVISION_TABLE,
                sa.Column(column_name, sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
            )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(REVISION_TABLE, conn):
        return
    existing = [name for name in COLUMN_NAMES if migration.column_exists(REVISION_TABLE, name, conn)]
    if not existing:
        return
    with op.batch_alter_table(REVISION_TABLE) as batch_op:
        for column_name in existing:
            batch_op.drop_column(column_name)
