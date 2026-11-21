"""Merge release and maintenance migration heads.

Revision ID: 56827e37fd6f
Revises: 6b4d1e9c7a25, c8f2a4e6b9d1
Create Date: 2026-11-11

Phase: EXPAND

Join the release and maintenance histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "56827e37fd6f"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("6b4d1e9c7a25", "c8f2a4e6b9d1")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
