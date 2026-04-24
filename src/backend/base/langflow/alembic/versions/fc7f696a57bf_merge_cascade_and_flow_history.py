"""Merge cascade fix and flow version branches

Revision ID: fc7f696a57bf
Revises: 59a272d6669a, 2a5defa5ddc0
Create Date: 2026-03-05 12:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "fc7f696a57bf"
down_revision: tuple[str, str] = ("59a272d6669a", "2a5defa5ddc0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
