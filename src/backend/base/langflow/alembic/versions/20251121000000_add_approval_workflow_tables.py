"""Add approval workflow tables

Revision ID: 20251121000000
Revises: 20251120120000
Create Date: 2025-11-21 00:00:00.000000

This migration creates the tables needed for the flow approval workflow:
- flow_status: Lookup table for flow status values
- flow_version: Tracks versions submitted for approval
- version_flow_input_sample: Stores sample inputs for each version
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "20251121000000"
down_revision: Union[str, None] = "20251120120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create approval workflow tables."""
    conn = op.get_bind()

    # =========================================================================
    # 1. Create flow_status lookup table
    # =========================================================================
    if not migration.table_exists("flow_status", conn):
        op.create_table(
            "flow_status",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("status_name", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

        # Create unique index on status_name (combines unique constraint + index)
        op.create_index("ix_flow_status_status_name", "flow_status", ["status_name"], unique=True)

        # Seed initial status values
        op.execute("""
            INSERT INTO flow_status (status_name, description) VALUES
            ('Draft', 'Flow is being edited'),
            ('Submitted', 'Flow submitted for approval review'),
            ('Approved', 'Flow approved by admin'),
            ('Rejected', 'Flow rejected by admin'),
            ('Published', 'Flow published to marketplace'),
            ('Unpublished', 'Flow unpublished from marketplace'),
            ('Deleted', 'Flow marked for deletion')
        """)

    # =========================================================================
    # 2. Create flow_version table
    # =========================================================================
    if not migration.table_exists("flow_version", conn):
        op.create_table(
            "flow_version",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("original_flow_id", sa.UUID(), nullable=False),
            sa.Column("version_flow_id", sa.UUID(), nullable=True),
            sa.Column("status_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("agent_logo", sa.String(length=1000), nullable=True),
            sa.Column("sample_id", sa.UUID(), nullable=True),
            # Submission audit
            sa.Column("submitted_by", sa.UUID(), nullable=True),
            sa.Column("submitted_by_name", sa.String(length=255), nullable=True),
            sa.Column("submitted_by_email", sa.String(length=255), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            # Review audit
            sa.Column("reviewed_by", sa.UUID(), nullable=True),
            sa.Column("reviewed_by_name", sa.String(length=255), nullable=True),
            sa.Column("reviewed_by_email", sa.String(length=255), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            # Publish audit
            sa.Column("published_by", sa.UUID(), nullable=True),
            sa.Column("published_by_name", sa.String(length=255), nullable=True),
            sa.Column("published_by_email", sa.String(length=255), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            # Standard audit
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            # Primary key
            sa.PrimaryKeyConstraint("id"),
            # Foreign keys
            sa.ForeignKeyConstraint(["original_flow_id"], ["flow.id"], name="fk_flow_version_original_flow"),
            sa.ForeignKeyConstraint(["version_flow_id"], ["flow.id"], name="fk_flow_version_version_flow"),
            sa.ForeignKeyConstraint(["status_id"], ["flow_status.id"], name="fk_flow_version_status"),
            sa.ForeignKeyConstraint(["submitted_by"], ["user.id"], name="fk_flow_version_submitted_by"),
            sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"], name="fk_flow_version_reviewed_by"),
            sa.ForeignKeyConstraint(["published_by"], ["user.id"], name="fk_flow_version_published_by"),
            # Unique constraint: version must be unique per original flow
            sa.UniqueConstraint("original_flow_id", "version", name="uq_flow_version_original_flow_version"),
        )

        # Create indexes
        op.create_index("ix_flow_version_original_flow_id", "flow_version", ["original_flow_id"])
        op.create_index("ix_flow_version_version_flow_id", "flow_version", ["version_flow_id"])
        op.create_index("ix_flow_version_status_id", "flow_version", ["status_id"])
        op.create_index("ix_flow_version_submitted_by", "flow_version", ["submitted_by"])

    # =========================================================================
    # 3. Create version_flow_input_sample table
    # =========================================================================
    if not migration.table_exists("version_flow_input_sample", conn):
        op.create_table(
            "version_flow_input_sample",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("flow_version_id", sa.UUID(), nullable=False),
            sa.Column("original_flow_id", sa.UUID(), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False),
            sa.Column("storage_account", sa.Text(), nullable=True),
            sa.Column("container_name", sa.Text(), nullable=True),
            sa.Column("file_names", sa.JSON(), nullable=True),
            sa.Column("sample_text", sa.JSON(), nullable=True),
            sa.Column("sample_output", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            # Primary key
            sa.PrimaryKeyConstraint("id"),
            # Foreign keys
            sa.ForeignKeyConstraint(
                ["flow_version_id"],
                ["flow_version.id"],
                name="fk_version_flow_input_sample_flow_version",
                ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["original_flow_id"],
                ["flow.id"],
                name="fk_version_flow_input_sample_original_flow"
            ),
        )

        # Create indexes
        op.create_index("ix_version_flow_input_sample_flow_version_id", "version_flow_input_sample", ["flow_version_id"])
        op.create_index("ix_version_flow_input_sample_original_flow_id", "version_flow_input_sample", ["original_flow_id"])


def downgrade() -> None:
    """Drop approval workflow tables."""
    conn = op.get_bind()

    # Drop version_flow_input_sample table
    if migration.table_exists("version_flow_input_sample", conn):
        op.drop_index("ix_version_flow_input_sample_original_flow_id", table_name="version_flow_input_sample")
        op.drop_index("ix_version_flow_input_sample_flow_version_id", table_name="version_flow_input_sample")
        op.drop_table("version_flow_input_sample")

    # Drop flow_version table
    if migration.table_exists("flow_version", conn):
        op.drop_index("ix_flow_version_submitted_by", table_name="flow_version")
        op.drop_index("ix_flow_version_status_id", table_name="flow_version")
        op.drop_index("ix_flow_version_version_flow_id", table_name="flow_version")
        op.drop_index("ix_flow_version_original_flow_id", table_name="flow_version")
        op.drop_table("flow_version")

    # Drop flow_status table
    if migration.table_exists("flow_status", conn):
        op.drop_index("ix_flow_status_status_name", table_name="flow_status")
        op.drop_table("flow_status")
