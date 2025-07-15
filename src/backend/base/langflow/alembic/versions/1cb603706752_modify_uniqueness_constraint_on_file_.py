"""Modify uniqueness constraint on file names

Revision ID: 1cb603706752
Revises: d9a6ea21edcd
Create Date: 2025-07-11 07:02:14.896583
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '1cb603706752'
down_revision: Union[str, None] = 'd9a6ea21edcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# -- Shared schema definition to avoid drift
file_table_columns = [
    sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), primary_key=True, nullable=False),
    sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
    sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column("size", sa.Integer(), nullable=False),
    sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_file_user_id_user"),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    is_sqlite = conn.dialect.name == "sqlite"

    # Detect current unique constraint on 'name'
    constraints = inspector.get_unique_constraints("file")
    name_constraint = next(
        (c["name"] for c in constraints if c["column_names"] == ["name"]),
        None,
    )

    if is_sqlite:
        # SQLite: Recreate table with composite constraint
        op.create_table(
            "file_new",
            *file_table_columns,
            sa.UniqueConstraint("name", "user_id", name="file_name_user_id_key"),
        )

        op.execute(sa.text("""
            INSERT INTO file_new (
                id, user_id, name, path, size, provider, created_at, updated_at
            )
            SELECT id, user_id, name, path, size, provider, created_at, updated_at
            FROM file
        """))

        op.drop_table("file")
        op.rename_table("file_new", "file")

    else:
        # PostgreSQL: Drop old unique, add new composite
        with op.batch_alter_table("file") as batch_op:
            if name_constraint:
                batch_op.drop_constraint(name_constraint, type_="unique")
            batch_op.create_unique_constraint("file_name_user_id_key", ["name", "user_id"])

    inspector = inspect(conn)  # Refresh after schema changes
    indexes = inspector.get_indexes("file")
    if not any(i["column_names"] == ["user_id"] for i in indexes):
        op.create_index("ix_file_user_id", "file", ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    is_sqlite = conn.dialect.name == "sqlite"

    # Pre-check for duplicates on 'name' across users
    duplicate_check = sa.text("""
        SELECT name, COUNT(*) as count
        FROM file
        GROUP BY name
        HAVING count > 1
    """)
    duplicates = conn.execute(duplicate_check).fetchall()
    if duplicates:
        duplicate_names = [row[0] for row in duplicates]
        raise ValueError(
            f"Downgrade aborted: Duplicate file names exist across users: {duplicate_names}. "
            f"To resolve, rename conflicting files or manually handle the migration."
        )
    
    # Drop user_id index (only for PostgreSQL - SQLite will recreate table)
    if not is_sqlite:
        indexes = inspector.get_indexes("file")
        user_id_index = next(
            (i["name"] for i in indexes if i["column_names"] == ["user_id"]),
            None,
        )
        if user_id_index:
            op.drop_index(user_id_index, table_name="file")

    if is_sqlite:
        # SQLite: Recreate table with single column constraint
        op.create_table(
            "file_new",
            *file_table_columns,
            sa.UniqueConstraint("name", name="file_name_key"),
        )

        op.execute(sa.text("""
            INSERT INTO file_new (
                id, user_id, name, path, size, provider, created_at, updated_at
            )
            SELECT id, user_id, name, path, size, provider, created_at, updated_at
            FROM file
        """))

        op.drop_table("file")
        op.rename_table("file_new", "file")

    else:
        # PostgreSQL: Drop composite constraint, add single column constraint
        with op.batch_alter_table("file") as batch_op:
            constraints = inspector.get_unique_constraints("file")
            composite_constraint = next(
                (c["name"] for c in constraints if set(c["column_names"]) == {"name", "user_id"}),
                None,
            )
            if composite_constraint:
                batch_op.drop_constraint(composite_constraint, type_="unique")
                batch_op.create_unique_constraint("file_name_key", ["name"])
            else:
                raise ValueError(
                    "Composite unique constraint on 'name' and 'user_id' not found; "
                    "schema may have drifted from expected state."
                )
