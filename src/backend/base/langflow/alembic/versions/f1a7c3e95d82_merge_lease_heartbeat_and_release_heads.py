"""merge lease heartbeat and release heads

Phase: EXPAND (no DDL - merge point only)

Revision ID: f1a7c3e95d82
Revises: c6a81d3e9502, e3b7d1c4a95f
Create Date: 2026-10-28 15:41:18.332014

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f1a7c3e95d82"  # pragma: allowlist secret
down_revision: str | None = ("c6a81d3e9502", "e3b7d1c4a95f")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
