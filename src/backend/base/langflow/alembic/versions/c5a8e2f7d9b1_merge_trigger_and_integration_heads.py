"""Merge trigger and integration governance migration heads.

Revision ID: c5a8e2f7d9b1
Revises: b7c4e1a9d3f2, b4c7d2e8f1a3
Create Date: 2026-09-15

Phase: EXPAND
"""

revision = "c5a8e2f7d9b1"  # pragma: allowlist secret
down_revision = ("b7c4e1a9d3f2", "b4c7d2e8f1a3")  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
