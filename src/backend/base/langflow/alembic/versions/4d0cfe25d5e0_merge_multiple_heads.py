"""Merge multiple heads.

Revision ID: 4d0cfe25d5e0
Revises: 50bdbf646c1c, d37bc4322900
Create Date: 2025-10-16 12:53:31.528895

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "4d0cfe25d5e0"
down_revision: str | None = ("50bdbf646c1c", "d37bc4322900")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
