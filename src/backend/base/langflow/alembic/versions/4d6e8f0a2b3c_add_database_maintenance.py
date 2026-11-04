"""Add the shared maintenance switch.

Phase: EXPAND
Revision ID: 4d6e8f0a2b3c
Revises: f2d6b8c4a901
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d6e8f0a2b3c"  # pragma: allowlist secret
down_revision: str | None = "f2d6b8c4a901"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("maintenance_state"):
        op.create_table(
            "maintenance_state",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("reason", sa.String(1024), nullable=True),
            sa.Column("set_by", sa.Uuid(), nullable=True),
            sa.Column("set_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("id = 1", name=op.f("ck_maintenance_state_singleton")),
        )
    table = sa.table("maintenance_state", sa.column("id", sa.Integer()), sa.column("enabled", sa.Boolean()))
    if op.get_bind().execute(sa.select(table.c.id).where(table.c.id == 1)).first() is None:
        op.bulk_insert(table, [{"id": 1, "enabled": False}])


def downgrade() -> None:
    op.drop_table("maintenance_state")
