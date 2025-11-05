"""create published_flow_version table

Revision ID: 20251106000000
Revises: 20251028000000
Create Date: 2025-11-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "20251106000000"
down_revision: Union[str, None] = "20251028000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create published_flow_version table for versioning support."""
    conn = op.get_bind()
    inspector: Inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    # Only create table if it doesn't exist
    if "published_flow_version" not in table_names:
        # Create the table
        op.create_table(
            "published_flow_version",
            # Primary key - auto-increment integer
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            # User-defined version string
            sa.Column("version", sa.String(length=50), nullable=False),
            # Flow relationships
            sa.Column("flow_id_cloned_to", sa.UUID(), nullable=False),
            sa.Column("flow_id_cloned_from", sa.UUID(), nullable=False),
            sa.Column("published_flow_id", sa.UUID(), nullable=False),
            # Version metadata snapshot
            sa.Column("flow_name", sa.String(length=255), nullable=False),
            sa.Column("flow_icon", sa.String(length=1000), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            # Status
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            # Audit fields
            sa.Column("published_by", sa.UUID(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            # Primary key constraint
            sa.PrimaryKeyConstraint("id"),
            # Foreign key constraints
            sa.ForeignKeyConstraint(
                ["flow_id_cloned_to"],
                ["flow.id"],
            ),
            sa.ForeignKeyConstraint(
                ["flow_id_cloned_from"],
                ["flow.id"],
            ),
            sa.ForeignKeyConstraint(
                ["published_flow_id"],
                ["published_flow.id"],
            ),
            sa.ForeignKeyConstraint(
                ["published_by"],
                ["user.id"],
            ),
            # Unique constraint: version must be unique per original flow
            sa.UniqueConstraint(
                "flow_id_cloned_from",
                "version",
                name="uq_published_flow_version_flow_id_cloned_from_version",
            ),
        )

        # Partial unique index for active versions (PostgreSQL specific)
        # Ensures only one active version per published flow
        op.create_index(
            "uq_published_flow_version_one_active",
            "published_flow_version",
            ["published_flow_id", "active"],
            unique=True,
            postgresql_where=sa.text("active = true"),
        )

        # Migrate existing published_flow records to published_flow_version
        # This creates a v1 version for each existing published flow
        migrate_existing_data()


def migrate_existing_data() -> None:
    """Backfill existing published_flow records into published_flow_version table."""
    import json

    conn = op.get_bind()
    session = Session(bind=conn)

    # Query all published flows with status = 'PUBLISHED'
    result = conn.execute(
        sa.text("""
            SELECT
                id,
                flow_id,
                flow_cloned_from,
                version,
                flow_name,
                flow_icon,
                description,
                tags,
                published_by,
                published_at,
                created_at
            FROM published_flow
            WHERE status = 'PUBLISHED' AND flow_cloned_from IS NOT NULL
        """)
    )

    rows = result.fetchall()

    # Insert version records for each existing published flow
    for row in rows:
        # Convert tags to JSON string for JSONB column
        tags_value = json.dumps(row.tags) if row.tags else None

        conn.execute(
            sa.text("""
                INSERT INTO published_flow_version (
                    version,
                    flow_id_cloned_to,
                    flow_id_cloned_from,
                    published_flow_id,
                    flow_name,
                    flow_icon,
                    description,
                    tags,
                    active,
                    published_by,
                    published_at,
                    created_at
                ) VALUES (
                    :version,
                    :flow_id_cloned_to,
                    :flow_id_cloned_from,
                    :published_flow_id,
                    :flow_name,
                    :flow_icon,
                    :description,
                    :tags,
                    true,
                    :published_by,
                    :published_at,
                    :created_at
                )
            """),
            {
                "version": row.version or "v1",
                "flow_id_cloned_to": str(row.flow_id),
                "flow_id_cloned_from": str(row.flow_cloned_from),
                "published_flow_id": str(row.id),
                "flow_name": row.flow_name,
                "flow_icon": row.flow_icon,
                "description": row.description,
                "tags": tags_value,
                "published_by": str(row.published_by),
                "published_at": row.published_at,
                "created_at": row.created_at,
            },
        )

    session.commit()


def downgrade() -> None:
    """Drop published_flow_version table."""
    # Drop partial unique index
    op.drop_index("uq_published_flow_version_one_active", table_name="published_flow_version")

    # Drop table
    op.drop_table("published_flow_version")
