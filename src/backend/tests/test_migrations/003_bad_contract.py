"""Test migration - BAD CONTRACT phase.

Phase: CONTRACT

Revision ID: test003
"""  # noqa: N999

import sqlalchemy as sa
from alembic import op

revision = "test003"
down_revision = None


def upgrade():
    # ❌ Bad: No verification before dropping
    op.drop_column("users", "old_email")

    # ❌ Bad: Adding new column in CONTRACT phase
    op.add_column("users", sa.Column("new_field", sa.String()))


def downgrade():
    pass
