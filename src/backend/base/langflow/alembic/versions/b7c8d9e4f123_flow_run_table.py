"""
b7c8d9e4f123_flow_run_table

Revision ID: b7c8d9e4f123
Revises: 1b8b740a6fa3
Create Date: 2025-04-27 16:09:10
"""

# Alembic revision identifiers, used by Alembic.
revision = 'b7c8d9e4f123'
down_revision = 'e56d87f8994a'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
import sqlmodel

def upgrade():
    op.create_table(
        "flow_run",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("flow_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, index=True, default="pending"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

def downgrade():
    op.drop_table("flow_run")
