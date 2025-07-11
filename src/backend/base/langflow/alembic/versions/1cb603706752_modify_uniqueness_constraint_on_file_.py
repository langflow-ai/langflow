"""Modify uniqueness constraint on file names

Revision ID: 1cb603706752
Revises: d9a6ea21edcd
Create Date: 2025-07-11 07:02:14.896583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '1cb603706752'
down_revision: Union[str, None] = 'd9a6ea21edcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    is_sqlite = conn.dialect.name == "sqlite"

    # Get existing unique constraints
    constraints = inspector.get_unique_constraints("file")
    name_constraint = None
    for constraint in constraints:
        if constraint["column_names"] == ["name"]:
            name_constraint = constraint["name"]
            break

    if is_sqlite:
        # SQLite: Recreate the table to drop the unique constraint and add the new one
        # Step 1: Create a new table with the desired schema
        op.create_table(
            "file_new",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_file_user_id_user"),
            sa.UniqueConstraint("name", "user_id", name="file_name_user_id_key"),
        )

        # Step 2: Copy data
        op.execute(sa.text("""
            INSERT INTO file_new (
                id, user_id, name, path, size, provider, created_at, updated_at
            )
            SELECT id, user_id, name, path, size, provider, created_at, updated_at
            FROM file
        """))

        # Step 3: Drop and rename
        op.execute(sa.text("DROP TABLE file"))
        op.execute(sa.text("ALTER TABLE file_new RENAME TO file"))
    else:
        # PostgreSQL: Drop the existing unique constraint and add the new one
        with op.batch_alter_table("file", schema=None) as batch_op:
            if name_constraint:
                batch_op.drop_constraint(name_constraint, type_="unique")
            batch_op.create_unique_constraint(
                "file_name_user_id_key", ["name", "user_id"]
            )


def downgrade() -> None:
    conn = op.get_bind()
    is_sqlite = conn.dialect.name == "sqlite"

    if is_sqlite:
        # Step 1: Create the new table with the original UNIQUE constraint on "name"
        op.create_table(
            "file_new",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_file_user_id_user"),
            sa.UniqueConstraint("name", name="file_name_key"),
        )

        # Step 2: Copy the data
        op.execute(sa.text("""
            INSERT INTO file_new (
                id, user_id, name, path, size, provider, created_at, updated_at
            )
            SELECT id, user_id, name, path, size, provider, created_at, updated_at
            FROM file
        """))

        # Step 3: Drop and rename
        op.drop_table("file")
        op.rename_table("file_new", "file")
    else:
        # PostgreSQL: Drop the composite constraint and restore the original
        with op.batch_alter_table("file", schema=None) as batch_op:
            batch_op.drop_constraint("file_name_user_id_key", type_="unique")
            batch_op.create_unique_constraint("file_name_key", ["name"])
