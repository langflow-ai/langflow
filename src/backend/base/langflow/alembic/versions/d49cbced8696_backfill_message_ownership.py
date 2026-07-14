"""Backfill legacy message ownership from the owning flow.

Revision ID: d49cbced8696
Revises: 90c977dcf0f1
Create Date: 2026-07-14 00:00:02.000000

Phase: MIGRATE
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d49cbced8696"  # pragma: allowlist secret
down_revision: str | None = "90c977dcf0f1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_message_user_ids(conn: sa.Connection) -> None:
    flow = sa.table("flow", sa.column("id", sa.Uuid()), sa.column("user_id", sa.Uuid()))
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
    # Irreversible: migrated owners cannot be distinguished from runtime owners.
    return
