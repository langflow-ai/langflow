"""Merge the anonymous access revocation and 1.14.0 migration heads.

Revision ID: a09a699afb52
Revises: 7a4c2e9b6d15, b7c9d1e3f508
Create Date: 2026-11-24

Phase: EXPAND
"""

from collections.abc import Sequence

revision: str = "a09a699afb52"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = (
    "7a4c2e9b6d15",  # pragma: allowlist secret
    "b7c9d1e3f508",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
