"""add application_config table

Revision ID: 20251027120000
Revises: 99999999999
Create Date: 2025-10-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "20251027120000"
down_revision: Union[str, None] = "99999999999"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create application_config table for organization-wide settings."""
    conn = op.get_bind()
    inspector: Inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    # Create table if it doesn't exist
    if "application_config" not in table_names:
        op.create_table(
            "application_config",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("type", sa.String(), nullable=True, server_default="string"),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_by", sa.UUID(), nullable=True),
            sa.ForeignKeyConstraint(
                ["updated_by"],
                ["user.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", name="unique_config_key"),
        )

    # Create index if it doesn't exist
    indexes = inspector.get_indexes("application_config") if "application_config" in table_names else []
    if "ix_application_config_key" not in [index["name"] for index in indexes]:
        with op.batch_alter_table("application_config", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_application_config_key"), ["key"], unique=False)


def downgrade() -> None:
    """Drop application_config table."""
    op.drop_index(op.f("ix_application_config_key"), table_name="application_config")
    op.drop_table("application_config")
