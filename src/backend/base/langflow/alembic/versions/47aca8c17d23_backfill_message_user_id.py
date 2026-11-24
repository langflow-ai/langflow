"""Backfill legacy message ownership from the owning flow.

Phase: MIGRATE

Existing messages predate the nullable ``message.user_id`` column added by
``9b3e7c1f0a52``. Authenticated Agent and Memory runs now scope history by that
column, so leaving legacy rows NULL makes upgraded conversations disappear from
runtime memory even though they remain visible in the Playground.

Legacy rows do not retain enough provenance to reconstruct the original executor. The
flow owner is the only stable authorized principal for those rows, so NULL owners are
attributed to a matching flow's non-NULL ``user_id``. This restores owner/Playground
history while keeping legacy rows unavailable to arbitrary non-owner runners. Existing
non-NULL message owners and orphaned or ownerless rows are left unchanged.

Revision ID: 47aca8c17d23
Revises: 0819aa415ead
Create Date: 2026-07-13 16:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "47aca8c17d23"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "0819aa415ead"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_message_user_ids(conn: sa.Connection) -> None:
    flow = sa.table(
        "flow",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
    )
    message = sa.table(
        "message",
        sa.column("flow_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
    )

    owner_id = (
        sa.select(flow.c.user_id)
        .where(flow.c.id == message.c.flow_id)
        .where(flow.c.user_id.is_not(None))
        .correlate(message)
        .scalar_subquery()
    )
    conn.execute(
        message.update()
        .where(message.c.user_id.is_(None))
        .where(message.c.flow_id.is_not(None))
        .where(owner_id.is_not(None))
        .values(user_id=owner_id)
    )


def upgrade() -> None:
    _backfill_message_user_ids(op.get_bind())


def downgrade() -> None:
    # The backfill is intentionally irreversible: after upgrade there is no
    # durable way to distinguish a migrated owner from one written at runtime.
    return
