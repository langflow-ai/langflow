"""Add user.retired_at.

Phase: EXPAND
Revision ID: c3e1d5a7f902
Revises: f2a7c9e4b681

With AUTO_LOGIN off, startup retires the default superuser when it owns work
and has never signed in: it deactivates the account instead of deleting it.
retired_at records that this happened, so later restarts leave the account
alone and an admin who reactivates it is not undone. Nullable, no backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "c3e1d5a7f902"  # pragma: allowlist secret
down_revision: str | None = "f2a7c9e4b681"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("user", schema=None) as batch_op:
        if not migration.column_exists("user", "retired_at", conn):
            batch_op.add_column(sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("user", schema=None) as batch_op:
        if migration.column_exists("user", "retired_at", conn):
            batch_op.drop_column("retired_at")
