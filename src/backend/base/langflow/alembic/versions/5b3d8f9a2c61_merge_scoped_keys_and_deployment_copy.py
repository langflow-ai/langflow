"""Merge scoped API keys and deployment-copy release heads.

Revision ID: 5b3d8f9a2c61
Revises: c4e6f8a0b2d9, b7e1d4a92c60
Create Date: 2026-11-05

Phase: EXPAND

Join both published migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "5b3d8f9a2c61"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("c4e6f8a0b2d9", "b7e1d4a92c60")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
