"""Track the registration of the last completed OAuth grant.

Revision ID: e4f6a8b2c1d3
Revises: 1d8d193028c8
Create Date: 2026-10-23

Phase: EXPAND
Safe to rollback: YES
Services compatible: Versions that do not read connection_oauth.completed_registration_id
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e4f6a8b2c1d3"  # pragma: allowlist secret -- migration revision identifier
down_revision: str | None = "1d8d193028c8"  # pragma: allowlist secret -- migration revision identifier
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if migration.column_exists("connection_oauth", "completed_registration_id", conn):
        return
    with op.batch_alter_table("connection_oauth") as batch_op:
        batch_op.add_column(sa.Column("completed_registration_id", sa.String(length=120), nullable=True))
    op.execute(
        """
        UPDATE connection_oauth
        SET completed_registration_id = registration_id
        WHERE state_digest IS NULL
          AND EXISTS (
              SELECT 1 FROM "connection"
              WHERE "connection".id = connection_oauth.connection_id
                AND "connection".status = 'ready'
                AND "connection".status_reason IS NULL
          )
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.column_exists("connection_oauth", "completed_registration_id", conn):
        return
    with op.batch_alter_table("connection_oauth") as batch_op:
        batch_op.drop_column("completed_registration_id")
