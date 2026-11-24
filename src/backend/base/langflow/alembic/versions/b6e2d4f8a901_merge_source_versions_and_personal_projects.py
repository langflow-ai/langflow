"""Merge trigger source versions and personal project migration heads.

Revision ID: b6e2d4f8a901
Revises: a7c9e4b681f2, d8f2c3a4b5e6
Create Date: 2026-09-28

Phase: EXPAND

Join both existing histories without changing their revisions or the schema.
"""

from collections.abc import Sequence

revision: str = "b6e2d4f8a901"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("a7c9e4b681f2", "d8f2c3a4b5e6")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
