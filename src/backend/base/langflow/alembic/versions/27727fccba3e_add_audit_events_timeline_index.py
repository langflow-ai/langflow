"""Index audit_events by (timestamp, id) for the unified audit feed.

Revision ID: 27727fccba3e
Revises: df1410b1eefa
Create Date: 2026-09-21

Phase: EXPAND

Additive only: one new index. The unified feed and its export read every
resource type newest first; without this index each page sorts the whole table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision = "27727fccba3e"  # pragma: allowlist secret
down_revision = "df1410b1eefa"  # pragma: allowlist secret
branch_labels = None
depends_on = None

TABLE = "audit_events"
INDEX = "ix_audit_events_timeline"


def _has_index(bind) -> bool:
    return any(index["name"] == INDEX for index in sa.inspect(bind).get_indexes(TABLE))


def upgrade() -> None:
    bind = op.get_bind()
    if not migration.table_exists(TABLE, bind) or _has_index(bind):
        return
    op.create_index(INDEX, TABLE, ["timestamp", "id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not migration.table_exists(TABLE, bind) or not _has_index(bind):
        return
    op.drop_index(INDEX, table_name=TABLE)
