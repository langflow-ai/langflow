"""Merge multiple heads.

Revision ID: c263b157d227
Revises: d37bc4322900, e5fc330efa7c
Create Date: 2025-10-16 10:30:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c263b157d227"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("d37bc4322900", "e5fc330efa7c")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge multiple heads - no changes needed."""


def downgrade() -> None:
    """Downgrade merge - no changes needed."""
