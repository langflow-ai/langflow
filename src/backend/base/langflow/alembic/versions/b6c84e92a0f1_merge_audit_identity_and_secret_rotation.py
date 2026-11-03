"""Merge represented audit identity and secret rotation migrations.

Revision ID: b6c84e92a0f1
Revises: a6f81c2d903b, c6a81d3e9502
Phase: EXPAND
"""

revision = "b6c84e92a0f1"  # pragma: allowlist secret
down_revision = ("a6f81c2d903b", "c6a81d3e9502")  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join both additive revisions without changing their schemas or history."""


def downgrade() -> None:
    """Restore both revision heads without changing their schemas or history."""
