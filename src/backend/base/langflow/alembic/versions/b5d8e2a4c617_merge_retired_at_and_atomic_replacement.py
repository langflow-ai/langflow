"""Merge the retired superuser and atomic project replacement migration histories.

Revision ID: b5d8e2a4c617
Revises: c3e1d5a7f902, f194a1b2c3d4
Create Date: 2026-09-30

Phase: EXPAND
Safe to rollback: YES (this merge has no schema operations)
Services compatible: No schema changes; preserves both existing histories.
"""

from collections.abc import Sequence

revision: str = "b5d8e2a4c617"  # pragma: allowlist secret - Alembic revision
down_revision: str | Sequence[str] | None = ("c3e1d5a7f902", "f194a1b2c3d4")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
