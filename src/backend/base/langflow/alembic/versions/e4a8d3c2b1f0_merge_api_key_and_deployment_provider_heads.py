"""Merge api key and deployment provider heads

Revision ID: e4a8d3c2b1f0
Revises: d306e5c17c41, 7f8e9d0c1b2a
Create Date: 2026-04-24 15:20:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e4a8d3c2b1f0"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("d306e5c17c41", "7f8e9d0c1b2a")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
