"""Merge background metrics and the release migration merge heads.

Both parent revisions have already joined published migration histories.
Join the parents without rewriting those histories so database startup can
resolve ``head`` after updating the release branch.

Revision ID: d6f8a0c2e4b9
Revises: a6d8e0f2b4c7, b5d8e2a4c617
Create Date: 2026-09-30

Phase: EXPAND
Safe to rollback: YES (no schema or data changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d6f8a0c2e4b9"  # pragma: allowlist secret
down_revision: tuple[str, str] = (
    "a6d8e0f2b4c7",  # pragma: allowlist secret
    "b5d8e2a4c617",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the migration heads without changing schema or data."""


def downgrade() -> None:
    """Restore the parent heads without reverting their schema changes."""
