"""Merge the audit events and storage retirement heads.

``release-1.13.0`` advanced to ``d42f18a9b760`` while the audit events table and
its timeline index were being written on top of the earlier head, so two heads
exist once the branches meet. Join the parents without rewriting either
published history, so database startup can resolve ``head`` again.

Revision ID: f3a9c1d7b025
Revises: 27727fccba3e, d42f18a9b760
Create Date: 2026-10-06

Phase: EXPAND
Safe to rollback: YES (no schema or data changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f3a9c1d7b025"  # pragma: allowlist secret
down_revision: tuple[str, str] = (
    "27727fccba3e",  # pragma: allowlist secret
    "d42f18a9b760",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the migration heads without changing schema or data."""


def downgrade() -> None:
    """Restore the parent heads without reverting their schema changes."""
