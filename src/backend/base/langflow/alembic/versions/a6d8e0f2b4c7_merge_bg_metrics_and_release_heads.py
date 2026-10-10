"""Merge background metrics, user retirement, and project replacement heads.

These independently published migration branches share earlier release
revisions. Join their heads so database startup can resolve ``head`` while
preserving upgrades from every existing revision.

Revision ID: a6d8e0f2b4c7
Revises: e2c4a6f8b0d3, c3e1d5a7f902, f194a1b2c3d4
Create Date: 2026-09-30

Phase: EXPAND
Safe to rollback: YES (no schema or data changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a6d8e0f2b4c7"  # pragma: allowlist secret
down_revision: tuple[str, str, str] = (
    "e2c4a6f8b0d3",  # pragma: allowlist secret
    "c3e1d5a7f902",  # pragma: allowlist secret
    "f194a1b2c3d4",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the migration heads without changing schema or data."""


def downgrade() -> None:
    """Restore the parent heads without reverting their schema changes."""
