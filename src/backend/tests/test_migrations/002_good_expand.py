"""Test migration - GOOD EXPAND phase.

Phase: EXPAND
Safe to rollback: YES

Revision ID: test002
"""  # noqa: N999

import sqlalchemy as sa
from alembic import op

revision = "test002"
down_revision = None


def upgrade():
    """EXPAND PHASE: Add new columns."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("users")]

    # ✅ Good: nullable column with existence check
    if "email_verified" not in columns:
        op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=True, server_default="false"))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("users")]

    if "email_verified" in columns:
        op.drop_column("users", "email_verified")
