"""Merge maintenance and worker release histories.

Phase: EXPAND

Revision ID: 2a4c6e8f0b1d
Revises: e6f8a0b2c4d6, f6a2c8e4b901

This revision joins existing histories without changing data or schema.
"""

from collections.abc import Sequence

revision: str = "2a4c6e8f0b1d"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("e6f8a0b2c4d6", "f6a2c8e4b901")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
