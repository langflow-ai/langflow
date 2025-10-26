"""add published flow table

Revision ID: 1234567890ab
Revises: d9a6ea21edcd
Create Date: 2025-01-21 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "1234567890ab"
down_revision: Union[str, None] = "d9a6ea21edcd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create published_flow table for marketplace functionality."""
    conn = op.get_bind()

    if not migration.table_exists("published_flow", conn):
        # Handle PostgreSQL ENUM creation properly
        db_dialect = conn.dialect.name

        def _create_enum_type_if_needed() -> None:
            """Create ENUM type if it doesn't exist, handling PostgreSQL specifically."""
            if db_dialect != "postgresql":
                return

            try:
                # Check if ENUM type already exists
                result = conn.execute(sa.text(
                    "SELECT 1 FROM pg_type WHERE typname = 'publish_status_enum'"
                ))
                enum_exists = result.fetchone() is not None

                if not enum_exists:
                    # Create ENUM type manually
                    conn.execute(sa.text(
                        "CREATE TYPE publish_status_enum AS ENUM ('PUBLISHED', 'UNPUBLISHED')"
                    ))
                    conn.commit()

            except Exception as e:
                # Handle case where ENUM might be created concurrently
                if "already exists" not in str(e).lower():
                    raise

        def _get_status_column() -> sa.Column:
            """Get the status column with proper ENUM handling based on dialect."""
            if db_dialect == "postgresql":
                # For PostgreSQL, use raw type name to reference existing ENUM
                # This bypasses SQLAlchemy's ENUM creation mechanism completely
                from sqlalchemy.types import UserDefinedType

                class PublishStatusEnum(UserDefinedType):
                    cache_ok = True

                    def get_col_spec(self):
                        return "publish_status_enum"

                return sa.Column(
                    "status",
                    PublishStatusEnum(),
                    nullable=False,
                    server_default=sa.text("'PUBLISHED'")
                )
            else:
                # For other databases (SQLite, etc.), use standard ENUM
                return sa.Column(
                    "status",
                    sa.Enum("PUBLISHED", "UNPUBLISHED", name="publish_status_enum", create_type=True),
                    nullable=False,
                    server_default=sa.text("'PUBLISHED'")
                )

        # Create ENUM type first if needed (PostgreSQL only)
        _create_enum_type_if_needed()

        # Create table with proper status column
        op.create_table(
            "published_flow",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("flow_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("published_by", sa.UUID(), nullable=False),
            _get_status_column(),
            sa.Column("version", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("flow_cloned_from", sa.UUID(), nullable=True),
            sa.Column("flow_name", sa.String(length=255), nullable=True),
            sa.Column("flow_icon", sa.String(length=255), nullable=True),
            sa.Column("published_by_username", sa.String(length=255), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=False),
            sa.Column("unpublished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
            ),
            sa.ForeignKeyConstraint(
                ["flow_cloned_from"],
                ["flow.id"],
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
            ),
            sa.ForeignKeyConstraint(
                ["published_by"],
                ["user.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("flow_cloned_from", name="uq_published_flow_cloned_from"),
        )

        # Create indexes
        op.create_index("ix_published_flow_flow_id", "published_flow", ["flow_id"])
        op.create_index("ix_published_flow_flow_cloned_from", "published_flow", ["flow_cloned_from"])
        op.create_index("ix_published_flow_user_id", "published_flow", ["user_id"])
        op.create_index("ix_published_flow_status", "published_flow", ["status"])
        op.create_index("ix_published_flow_category", "published_flow", ["category"])
        op.create_index("ix_published_flow_published_at", "published_flow", ["published_at"])


def downgrade() -> None:
    """Drop published_flow table."""
    conn = op.get_bind()

    if migration.table_exists("published_flow", conn):
        # Drop indexes first
        op.drop_index("ix_published_flow_published_at", table_name="published_flow")
        op.drop_index("ix_published_flow_category", table_name="published_flow")
        op.drop_index("ix_published_flow_status", table_name="published_flow")
        op.drop_index("ix_published_flow_user_id", table_name="published_flow")
        op.drop_index("ix_published_flow_flow_cloned_from", table_name="published_flow")
        op.drop_index("ix_published_flow_flow_id", table_name="published_flow")

        # Drop table
        op.drop_table("published_flow")

        # Clean up ENUM type for PostgreSQL if no other tables use it
        db_dialect = conn.dialect.name
        if db_dialect == "postgresql":
            try:
                # Check if any other tables use this ENUM type
                result = conn.execute(sa.text("""
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE udt_name = 'publish_status_enum'
                """))
                count = result.scalar()

                # If no other tables use this ENUM, drop it
                if count == 0:
                    conn.execute(sa.text("DROP TYPE IF EXISTS publish_status_enum"))
                    conn.commit()

            except Exception:
                # Ignore errors during cleanup - ENUM might be used elsewhere
                # or might have already been dropped
                pass
