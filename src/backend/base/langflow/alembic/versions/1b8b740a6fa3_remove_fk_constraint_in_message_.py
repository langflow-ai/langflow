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

def constraint_exists(constraint_name: str, conn) -> bool:
    """Check if a constraint with the given name already exists in the database.

    Args:
        constraint_name: The name of the constraint to check
        conn: SQLAlchemy connection

    Returns:
        bool: True if the constraint exists, False otherwise
    """
    inspector = Inspector.from_engine(conn)

    # Get all table names
    tables = inspector.get_table_names()

    # Check each table for the constraint
    for table in tables:
        for constraint in inspector.get_pk_constraint(table).get("name"), *[c.get("name") for c in inspector.get_foreign_keys(table)]:
            if constraint == constraint_name:
                return True

    return False

def upgrade() -> None:
    conn = op.get_bind()

    # For SQLite, we need to recreate the tables without the constraints
    # This approach preserves all data while removing the constraints

    # 1. Handle vertex_build table
    if migration.table_exists("vertex_build", conn):
        # Create a temporary table without the constraint
        temp_table_name = "temp_vertex_build"
        pk_name = "pk_vertex_build"

        # Check if PK constraint already exists
        if constraint_exists(pk_name, conn):
            # Use a different PK name if it already exists
            pk_name = f"pk_temp_vertex_build"

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
            sa.PrimaryKeyConstraint("build_id", name=pk_name),
        )

        # Copy data - use a window function to ensure build_id uniqueness across SQLite, PostgreSQL and MySQL
        # Filter out rows where the original 'id' (vertex id) is NULL, as the new table requires it.
        op.execute(f'''
            INSERT INTO "{temp_table_name}" (timestamp, id, data, artifacts, params, build_id, flow_id, valid)
            SELECT timestamp, id, data, artifacts, params, build_id, flow_id, valid
            FROM (
                SELECT timestamp, id, data, artifacts, params, build_id, flow_id, valid,
                       ROW_NUMBER() OVER (PARTITION BY build_id ORDER BY timestamp) as rn
                FROM "vertex_build"
                WHERE id IS NOT NULL -- Ensure vertex id is not NULL
            ) sub
            WHERE rn = 1
        ''')

        # Drop original table and rename temp table
        op.drop_table("vertex_build")
        op.rename_table(temp_table_name, "vertex_build")

    # 2. Handle transaction table
    if migration.table_exists("transaction", conn):
        # Create a temporary table without the constraint
        temp_table_name = "temp_transaction"
        pk_name = "pk_transaction"

        # Check if PK constraint already exists
        if constraint_exists(pk_name, conn):
            # Use a different PK name if it already exists
            pk_name = f"pk_temp_transaction"

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
            sa.PrimaryKeyConstraint("id", name=pk_name),
        )

        # Copy data - explicitly list columns and filter out rows where id is NULL
        op.execute(f'''
            INSERT INTO "{temp_table_name}" (timestamp, vertex_id, target_id, inputs, outputs, status, id, flow_id, error)
            SELECT timestamp, vertex_id, target_id, inputs, outputs, status, id, flow_id, error
            FROM "transaction"
            WHERE id IS NOT NULL
        ''')

        # Drop original table and rename temp table
        op.drop_table("transaction")
        op.rename_table(temp_table_name, "transaction")

    # 3. Handle message table
    if migration.table_exists("message", conn):
        # Create a temporary table without the constraint
        temp_table_name = "temp_message"
        pk_name = "pk_message"

        # Check if PK constraint already exists
        if constraint_exists(pk_name, conn):
            # Use a different PK name if it already exists
            pk_name = f"pk_temp_message"

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
            sa.PrimaryKeyConstraint("id", name=pk_name),
        )

        # Copy data - explicitly list columns and filter out rows where id is NULL
        op.execute(f'''
            INSERT INTO "{temp_table_name}" (timestamp, sender, sender_name, session_id, text, id, flow_id, files, error, edit, properties, category, content_blocks)
            SELECT timestamp, sender, sender_name, session_id, text, id, flow_id, files, error, edit, properties, category, content_blocks
            FROM "message"
            WHERE id IS NOT NULL
        ''')

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
        pk_name = "pk_vertex_build"
        fk_name = "fk_vertex_build_flow_id_flow"

        # Check if constraints already exist
        if constraint_exists(pk_name, conn):
            pk_name = f"pk_temp_vertex_build"

        if constraint_exists(fk_name, conn):
            fk_name = f"fk_vertex_build_flow_id_flow_{revision[:8]}"

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
                name=fk_name,
            ),
            sa.PrimaryKeyConstraint("build_id", name=pk_name),
        )

        # Copy data - use a window function to ensure build_id uniqueness.
        # Filter out rows where build_id is NULL (PK constraint)
        # No need to filter by 'id' here as the target column allows NULLs.
        op.execute(f'''
            INSERT INTO "{temp_table_name}" (timestamp, id, data, artifacts, params, build_id, flow_id, valid)
            SELECT timestamp, id, data, artifacts, params, build_id, flow_id, valid
            FROM (
                SELECT timestamp, id, data, artifacts, params, build_id, flow_id, valid,
                       ROW_NUMBER() OVER (PARTITION BY build_id ORDER BY timestamp) as rn
                FROM "vertex_build"
                WHERE build_id IS NOT NULL -- Ensure primary key is not NULL
            ) sub
            WHERE rn = 1
        ''')

        # Drop original table and rename temp table
        op.drop_table("vertex_build")
        op.rename_table(temp_table_name, "vertex_build")

    # 2. Handle transaction table
    if migration.table_exists("transaction", conn):
        # Create a temporary table with the constraint
        temp_table_name = "temp_transaction"
        pk_name = "pk_transaction"
        fk_name = "fk_transaction_flow_id_flow"

        # Check if constraints already exist
        if constraint_exists(pk_name, conn):
            pk_name = f"pk_temp_transaction"

        if constraint_exists(fk_name, conn):
            fk_name = f"fk_transaction_flow_id_flow_{revision[:8]}"

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
                name=fk_name,
            ),
            sa.PrimaryKeyConstraint("id", name=pk_name),
        )

        # Copy data - explicitly list columns and filter out rows where id is NULL
        op.execute(f'''
            INSERT INTO "{temp_table_name}" (timestamp, vertex_id, target_id, inputs, outputs, status, id, flow_id, error)
            SELECT timestamp, vertex_id, target_id, inputs, outputs, status, id, flow_id, error
            FROM "transaction"
            WHERE id IS NOT NULL
        ''')

        # Drop original table and rename temp table
        op.drop_table("transaction")
        op.rename_table(temp_table_name, "transaction")

    # 3. Handle message table
    if migration.table_exists("message", conn):
        # Create a temporary table with the constraint
        temp_table_name = "temp_message"
        pk_name = "pk_message"
        fk_name = "fk_message_flow_id_flow"

        # Check if constraints already exist
        if constraint_exists(pk_name, conn):
            pk_name = f"pk_temp_message"

        if constraint_exists(fk_name, conn):
            fk_name = f"fk_message_flow_id_flow_{revision[:8]}"

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
                name=fk_name,
            ),
            sa.PrimaryKeyConstraint("id", name=pk_name),
        )

        # Copy data - explicitly list columns and filter out rows where id is NULL
        op.execute(f'''
            INSERT INTO "{temp_table_name}" (timestamp, sender, sender_name, session_id, text, id, flow_id, files, error, edit, properties, category, content_blocks)
            SELECT timestamp, sender, sender_name, session_id, text, id, flow_id, files, error, edit, properties, category, content_blocks
            FROM "message"
            WHERE id IS NOT NULL
        ''')

        # Drop original table and rename temp table
        op.drop_table("message")
        op.rename_table(temp_table_name, "message")
    # ### end Alembic commands ###
