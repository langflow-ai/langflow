"""add job table

Revision ID: a6faa131285d
Revises: e3162c1804e6
Create Date: 2024-12-23 10:54:57.844827

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.engine.reflection import Inspector

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = 'a6faa131285d'
down_revision: Union[str, None] = 'e3162c1804e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    # Create job table if it doesn't exist
    if "job" not in table_names:
        op.create_table(
            "job",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(length=191), primary_key=True),
            sa.Column("next_run_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("job_state", sa.LargeBinary(), nullable=True),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("flow_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], name="fk_job_flow_id_flow", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_job_user_id_user", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name="pk_job"),
        )

        # Create indices
        with op.batch_alter_table("job", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_job_name"), ["name"], unique=False)
            batch_op.create_index(batch_op.f("ix_job_flow_id"), ["flow_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_job_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    table_names = inspector.get_table_names()

    if "job" in table_names:
        # Drop indices first
        with op.batch_alter_table("job", schema=None) as batch_op:
            batch_op.drop_index("ix_job_name")
            batch_op.drop_index("ix_job_flow_id")
            batch_op.drop_index("ix_job_user_id")

        # Drop the table
        op.drop_table("job")
