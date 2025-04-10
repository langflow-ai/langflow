"""remove fk constraint in message transaction and vertex build


Revision ID: 1b8b740a6fa3
Revises: f3b2d1f1002d
Create Date: 2025-04-10 10:17:32.493181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '1b8b740a6fa3'
down_revision: Union[str, None] = 'f3b2d1f1002d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

def upgrade() -> None:
    conn = op.get_bind()

    # For SQLite, we need to recreate the tables without the constraints
    # This approach preserves all data while removing the constraints

    # 1. Handle vertex_build table
    if migration.table_exists("vertex_build", conn):
        # Create a temporary table without the constraint
        temp_table_name = "temp_vertex_build"

        # Create temp table with same schema but no FK constraint
        op.create_table(
            temp_table_name,
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("artifacts", sa.JSON(), nullable=True),
            sa.Column("params", sa.Text(), nullable=True),
            sa.Column("build_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("valid", sa.BOOLEAN(), nullable=False),
            sa.PrimaryKeyConstraint("build_id", name="pk_vertex_build"),
        )

        # Copy data - use quoted identifiers to avoid keyword issues
        op.execute('INSERT INTO "temp_vertex_build" SELECT * FROM "vertex_build"')

        # Drop original table and rename temp table
        op.drop_table("vertex_build")
        op.rename_table(temp_table_name, "vertex_build")

    # 2. Handle transaction table
    if migration.table_exists("transaction", conn):
        # Create a temporary table without the constraint
        temp_table_name = "temp_transaction"

        # Create temp table with same schema but no FK constraint
        op.create_table(
            temp_table_name,
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("vertex_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.PrimaryKeyConstraint("id", name="pk_transaction"),
        )

        # Copy data - use quoted identifiers to avoid keyword issues
        op.execute('INSERT INTO "temp_transaction" SELECT * FROM "transaction"')

        # Drop original table and rename temp table
        op.drop_table("transaction")
        op.rename_table(temp_table_name, "transaction")

    # 3. Handle message table
    if migration.table_exists("message", conn):
        # Create a temporary table without the constraint
        temp_table_name = "temp_message"

        # Create temp table with same schema but no FK constraint
        op.create_table(
            temp_table_name,
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("sender", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("sender_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=True),
            sa.Column("files", sa.JSON(), nullable=True),
            sa.Column("error", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("edit", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("properties", sa.JSON(), nullable=True),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("content_blocks", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id", name="pk_message"),
        )

        # Copy data - use quoted identifiers to avoid keyword issues
        op.execute('INSERT INTO "temp_message" SELECT * FROM "message"')

        # Drop original table and rename temp table
        op.drop_table("message")
        op.rename_table(temp_table_name, "message")


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    conn = op.get_bind()

    # Recreate tables with constraints
    # 1. Handle vertex_build table
    if migration.table_exists("vertex_build", conn):
        # Create a temporary table with the constraint
        temp_table_name = "temp_vertex_build"

        # Create temp table with same schema including FK constraint
        op.create_table(
            temp_table_name,
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("artifacts", sa.JSON(), nullable=True),
            sa.Column("params", sa.Text(), nullable=True),
            sa.Column("build_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("valid", sa.BOOLEAN(), nullable=False),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
                name="fk_vertex_build_flow_id_flow",
            ),
            sa.PrimaryKeyConstraint("build_id", name="pk_vertex_build"),
        )

        # Copy data - use quoted identifiers to avoid keyword issues
        op.execute('INSERT INTO "temp_vertex_build" SELECT * FROM "vertex_build"')

        # Drop original table and rename temp table
        op.drop_table("vertex_build")
        op.rename_table(temp_table_name, "vertex_build")

    # 2. Handle transaction table
    if migration.table_exists("transaction", conn):
        # Create a temporary table with the constraint
        temp_table_name = "temp_transaction"

        # Create temp table with same schema including FK constraint
        op.create_table(
            temp_table_name,
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("vertex_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
                name="fk_transaction_flow_id_flow",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_transaction"),
        )

        # Copy data - use quoted identifiers to avoid keyword issues
        op.execute('INSERT INTO "temp_transaction" SELECT * FROM "transaction"')

        # Drop original table and rename temp table
        op.drop_table("transaction")
        op.rename_table(temp_table_name, "transaction")

    # 3. Handle message table
    if migration.table_exists("message", conn):
        # Create a temporary table with the constraint
        temp_table_name = "temp_message"

        # Create temp table with same schema including FK constraint
        op.create_table(
            temp_table_name,
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("sender", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("sender_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=True),
            sa.Column("files", sa.JSON(), nullable=True),
            sa.Column("error", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("edit", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("properties", sa.JSON(), nullable=True),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("content_blocks", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["flow_id"],
                ["flow.id"],
                name="fk_message_flow_id_flow",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_message"),
        )

        # Copy data - use quoted identifiers to avoid keyword issues
        op.execute('INSERT INTO "temp_message" SELECT * FROM "message"')

        # Drop original table and rename temp table
        op.drop_table("message")
        op.rename_table(temp_table_name, "message")
    # ### end Alembic commands ###
