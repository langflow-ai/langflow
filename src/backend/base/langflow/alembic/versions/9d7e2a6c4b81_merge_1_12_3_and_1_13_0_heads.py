"""Merge the release 1.12.3 and 1.13.0 migration heads.

Revision ID: 9d7e2a6c4b81
Revises: 386662af02e9, e6f9a2b4c8d1
Create Date: 2026-09-22

Phase: EXPAND

Join the knowledge-base storage fix and trigger history without changing schema.
"""

from collections.abc import Sequence

revision: str = "9d7e2a6c4b81"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("386662af02e9", "e6f9a2b4c8d1")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
