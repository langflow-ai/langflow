"""added job_type to make jobs generic and user_id for ownership

Revision ID: 169b35510b37
Revises: 369268b9af8b
Create Date: 2026-02-10 16:15:51.830502

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "169b35510b37"  # pragma: allowlist secret
down_revision: str | None = "b1c2d3e4f5a6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Check which columns already exist (handles fresh DB where model creates them)
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("job")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("job")}
    job_type_enum = sa.Enum("workflow", "ingestion", "evaluation", name="job_type_enum")
    job_type_enum.create(conn, checkfirst=True)

    with op.batch_alter_table("job", schema=None) as batch_op:
        if "type" not in existing_columns:
            batch_op.add_column(sa.Column("type", job_type_enum, nullable=True))
        if "user_id" not in existing_columns:
            batch_op.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        if "ix_job_status" in existing_indexes:
            batch_op.drop_index(batch_op.f("ix_job_status"))
        if "ix_job_type" not in existing_indexes:
            batch_op.create_index(batch_op.f("ix_job_type"), ["type"], unique=False)
        if "ix_job_user_id" not in existing_indexes:
            batch_op.create_index(batch_op.f("ix_job_user_id"), ["user_id"], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("job")}

    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_job_user_id"))
        batch_op.drop_index(batch_op.f("ix_job_type"))
        batch_op.create_index(batch_op.f("ix_job_status"), ["status"], unique=False)
        batch_op.drop_column("user_id")
        batch_op.drop_column("type")

    if "type" in existing_columns:
        job_type_enum = sa.Enum("workflow", "ingestion", "evaluation", name="job_type_enum")
        job_type_enum.drop(conn, checkfirst=True)

    # ### end Alembic commands ###
