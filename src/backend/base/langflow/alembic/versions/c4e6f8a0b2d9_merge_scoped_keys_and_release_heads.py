"""Merge scoped API keys and release migration heads.

Revision ID: c4e6f8a0b2d9
Revises: a1e7b9c3d5f0, f2d6b8c4a901
Phase: EXPAND
"""

from collections.abc import Sequence

revision: str = "c4e6f8a0b2d9"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("a1e7b9c3d5f0", "f2d6b8c4a901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
