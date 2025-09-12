"""New fixes

Revision ID: bc2f01c40e4a
Revises: b2fa308044b5
Create Date: 2024-01-26 13:34:14.496769

"""

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bc2f01c40e4a"
down_revision: str | None = "b2fa308044b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    flow_columns = {column["name"] for column in inspector.get_columns("flow")}
    flow_indexes = {index["name"] for index in inspector.get_indexes("flow")}

    # Suppress the SQLite foreign key warning
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*SQL-parsed foreign key constraint.*")
        flow_fks = {fk["name"] for fk in inspector.get_foreign_keys("flow")}

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if "is_component" not in flow_columns:
            batch_op.add_column(sa.Column("is_component", sa.Boolean(), nullable=True))
        if "updated_at" not in flow_columns:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        if "folder" not in flow_columns:
            batch_op.add_column(sa.Column("folder", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        if "user_id" not in flow_columns:
            batch_op.add_column(sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=True))
        if "ix_flow_user_id" not in flow_indexes:
            batch_op.create_index(batch_op.f("ix_flow_user_id"), ["user_id"], unique=False)
        if "flow_user_id_fkey" not in flow_fks:
            batch_op.create_foreign_key("flow_user_id_fkey", "user", ["user_id"], ["id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    flow_columns = {column["name"] for column in inspector.get_columns("flow")}
    flow_indexes = {index["name"] for index in inspector.get_indexes("flow")}

    # Suppress the SQLite foreign key warning
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*SQL-parsed foreign key constraint.*")
        flow_fks = {fk["name"] for fk in inspector.get_foreign_keys("flow")}

    with op.batch_alter_table("flow", schema=None) as batch_op:
        if "flow_user_id_fkey" in flow_fks:
            batch_op.drop_constraint("flow_user_id_fkey", type_="foreignkey")
        if "ix_flow_user_id" in flow_indexes:
            batch_op.drop_index(batch_op.f("ix_flow_user_id"))
        if "user_id" in flow_columns:
            batch_op.drop_column("user_id")
        if "folder" in flow_columns:
            batch_op.drop_column("folder")
        if "updated_at" in flow_columns:
            batch_op.drop_column("updated_at")
        if "is_component" in flow_columns:
            batch_op.drop_column("is_component")
