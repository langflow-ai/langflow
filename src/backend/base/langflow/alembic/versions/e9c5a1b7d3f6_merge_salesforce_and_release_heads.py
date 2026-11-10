"""Merge Salesforce and release migration heads.

Revision ID: e9c5a1b7d3f6
Revises: e7b3d9a5c102, d7e9a1c3f5b8
Create Date: 2026-11-10

Phase: EXPAND

Join both migration histories without changing schema or data.
"""

from collections.abc import Sequence

revision: str = "e9c5a1b7d3f6"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("e7b3d9a5c102", "d7e9a1c3f5b8")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
