"""Synchronize denormalized flow workspace ids from their projects.

Phase: MIGRATE
Revision ID: b7d5f9a3c2e4
Revises: a6c4e2f8b1d3
Create Date: 2026-07-22 00:00:00.000000

Project membership is the authorization source of truth. Older rows could
carry a caller-supplied ``flow.workspace_id`` that disagreed with the owning
folder, so repair every project-scoped row before workspace grants are used as
a SQL list prefilter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b7d5f9a3c2e4"  # pragma: allowlist secret
down_revision: str | None = "a6c4e2f8b1d3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not (migration.table_exists("flow", conn) and migration.table_exists("folder", conn)):
        return
    required = (
        migration.column_exists("flow", "folder_id", conn)
        and migration.column_exists("flow", "workspace_id", conn)
        and migration.column_exists("folder", "workspace_id", conn)
    )
    if not required:
        return

    conn.execute(
        sa.text(
            """
            UPDATE flow
            SET workspace_id = (
                SELECT folder.workspace_id
                FROM folder
                WHERE folder.id = flow.folder_id
            )
            WHERE flow.folder_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM folder WHERE folder.id = flow.folder_id)
            """
        )
    )


def downgrade() -> None:
    """Data repair is intentionally irreversible."""
