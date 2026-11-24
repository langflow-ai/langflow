"""Merge background job metrics and release migration heads.

The release branch merged flow version tokens with personal default projects
independently of the background metrics merge. Join both published heads so
Alembic can resolve ``head`` without rewriting either upgrade path.

Revision ID: e2c4a6f8b0d3
Revises: c7e9b2d4f6a8, 4e7a2b9c1d05
Create Date: 2026-09-29

Phase: EXPAND
Safe to rollback: YES (no schema or data changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e2c4a6f8b0d3"  # pragma: allowlist secret
down_revision: tuple[str, str] = ("c7e9b2d4f6a8", "4e7a2b9c1d05")  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both migration heads without changing schema or data."""


def downgrade() -> None:
    """Restore both parent heads without reverting their schema changes."""
