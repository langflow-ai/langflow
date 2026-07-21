"""merge hitl checkpoints and release heads

Phase: EXPAND (no DDL - merge point only)

Revision ID: 9cbe2f682e12
Revises: 9d5e24d777bf, a1f4c9d27b30
Create Date: 2026-07-13 10:43:02.800991

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9cbe2f682e12"
down_revision: str | None = ("9d5e24d777bf", "a1f4c9d27b30")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
