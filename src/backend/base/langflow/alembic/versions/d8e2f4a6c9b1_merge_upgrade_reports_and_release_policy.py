"""Merge upgrade report history and release policy heads.

Revision ID: d8e2f4a6c9b1
Revises: 8f1a2b3c4d5e, e6f8a0b2c4d6
Create Date: 2026-11-09

Phase: EXPAND

Join both histories without changing schema.
"""

from collections.abc import Sequence

revision: str = "d8e2f4a6c9b1"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("8f1a2b3c4d5e", "e6f8a0b2c4d6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
