"""Test migration - BAD EXPAND phase.

This should fail validation.

Revision ID: test001
"""  # noqa: N999

import sqlalchemy as sa
from alembic import op

revision = "test001"
down_revision = None


def upgrade():
    # ❌ Bad: non-nullable column without default
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False))

    # ❌ Bad: dropping column in EXPAND phase
    op.drop_column("users", "old_field")


def downgrade():
    pass
