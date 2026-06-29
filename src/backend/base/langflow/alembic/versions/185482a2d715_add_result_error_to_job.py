"""add result and error columns to job table.

Revision ID: 185482a2d715
Revises: b7c4d8e9f012
Create Date: 2026-06-03 10:00:00.000000

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "185482a2d715"  # pragma: allowlist secret
down_revision: str | None = "b7c4d8e9f012"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = {col["name"] for col in sa.inspect(conn).get_columns("job")}

    with op.batch_alter_table("job", schema=None) as batch_op:
        if "result" not in existing_columns:
            batch_op.add_column(sa.Column("result", _JSON, nullable=True))
        if "error" not in existing_columns:
            batch_op.add_column(sa.Column("error", _JSON, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    existing_columns = {col["name"] for col in sa.inspect(conn).get_columns("job")}

    with op.batch_alter_table("job", schema=None) as batch_op:
        if "error" in existing_columns:
            batch_op.drop_column("error")
        if "result" in existing_columns:
            batch_op.drop_column("result")
