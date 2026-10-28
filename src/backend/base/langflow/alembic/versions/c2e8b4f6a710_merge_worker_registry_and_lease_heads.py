"""merge worker registry and lease heartbeat heads

Phase: EXPAND (no DDL - merge point only)

The worker registry table and the job lease heartbeat column were developed on
separate layers of the same stack, both off a4e8c2b6d931. A merge point rather
than re-parenting d9f4b2e7c508 onto f1a7c3e95d82: re-parenting would make
d9f4b2e7c508 the head, so any database already stamped at it would treat
upgrade as a no-op and never receive job.lease_heartbeat_at or the release
tables below it. The two migrations touch unrelated tables, so either order is
correct.

Revision ID: c2e8b4f6a710
Revises: d9f4b2e7c508, f1a7c3e95d82
Create Date: 2026-10-28 17:02:44.915003

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c2e8b4f6a710"  # pragma: allowlist secret
down_revision: str | None = ("d9f4b2e7c508", "f1a7c3e95d82")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
