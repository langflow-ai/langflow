"""Merge cascade fix and flow history branches

Revision ID: a1b2c3d4e5f7
Revises: 59a272d6669a, 7d327cfafab6
Create Date: 2026-03-05 12:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: tuple[str, str] = ("59a272d6669a", "7d327cfafab6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
