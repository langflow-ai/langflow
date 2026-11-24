"""Merge the 1.12.2 message history and 1.13.0 integration governance heads.

Revision ID: d2f6a8c1e9b4
Revises: a1b2c9d3e4f5, b4c7d2e8f1a3
Create Date: 2026-09-16

Phase: EXPAND

This revision joins the release histories without changing the schema.
"""

from collections.abc import Sequence

revision: str = "d2f6a8c1e9b4"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = ("a1b2c9d3e4f5", "b4c7d2e8f1a3")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
