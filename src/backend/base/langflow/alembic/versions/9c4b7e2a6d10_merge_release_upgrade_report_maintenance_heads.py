"""Merge the release and upgrade-check migration histories.

Revision ID: 9c4b7e2a6d10
Revises: 56827e37fd6f, d4c8a6f2b901
Create Date: 2026-11-11

Phase: EXPAND

Join the release's upgrade-report migrations with the branch's maintenance history.
"""

from collections.abc import Sequence

revision: str = "9c4b7e2a6d10"  # pragma: allowlist secret - Alembic revision
down_revision: str | Sequence[str] | None = (
    "56827e37fd6f",
    "d4c8a6f2b901",
)  # pragma: allowlist secret - Alembic revision
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
