"""Modify uniqueness constraint on file names

Revision ID: 1cb603706752
Revises: 3162e83e485f
Create Date: 2025-07-24 07:02:14.896583
"""

import os
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '1cb603706752'
down_revision: Union[str, None] = '3162e83e485f'
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
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_file_user_id_user"),
]


def handle_duplicates_before_upgrade(conn):
    """Handle duplicate file names within the same user before applying unique constraint."""
    import os
    
    # Find duplicates within each user (database-agnostic approach)
    duplicate_check = sa.text("""
        SELECT user_id, name, COUNT(*) as count
        FROM file
        GROUP BY user_id, name
        HAVING COUNT(*) > 1
    """)
    
    duplicates = conn.execute(duplicate_check).fetchall()
    
    if duplicates:
        print(f"Found {len(duplicates)} sets of duplicate files. Renaming...")
        
        for row in duplicates:
            user_id, name, count = row
            
            # Get all file IDs for this user/name combination, ordered by creation date
            file_ids_query = sa.text("""
                SELECT id FROM file 
                WHERE user_id = :user_id AND name = :name 
                ORDER BY created_at
            """)
            
            file_ids = conn.execute(file_ids_query, {
                'user_id': user_id, 
                'name': name
            }).fetchall()
            
            # Skip the first (oldest) file, rename the rest
            for i, (file_id,) in enumerate(file_ids[1:], start=2):
                # Generate new name with suffix
                if '.' in name:
                    base_name, ext = name.rsplit('.', 1)
                    new_name = f"{base_name}_{i}.{ext}"
                else:
                    new_name = f"{name}_{i}"
                
                # Ensure the new name doesn't already exist for this user
                counter = i
                while True:
                    check_query = sa.text("""
                        SELECT COUNT(*) FROM file 
                        WHERE user_id = :user_id AND name = :name
                    """)
                    exists = conn.execute(check_query, {
                        'user_id': user_id, 
                        'name': new_name
                    }).scalar()
                    
                    if exists == 0:
                        break
                    
                    counter += 1
                    if '.' in name:
                        base_name, ext = name.rsplit('.', 1)
                        new_name = f"{base_name}_{counter}.{ext}"
                    else:
                        new_name = f"{name}_{counter}"
                
                # Rename the file
                update_query = sa.text("""
                    UPDATE file SET name = :new_name 
                    WHERE id = :file_id
                """)
                conn.execute(update_query, {
                    'new_name': new_name,
                    'file_id': file_id
                })
                
                print(f"Renamed duplicate file {file_id}: '{name}' -> '{new_name}'")


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    is_sqlite = conn.dialect.name == "sqlite"

    # Handle duplicates BEFORE applying the unique constraint
    handle_duplicates_before_upgrade(conn)

    # Detect current unique constraint on 'name'
    constraints = inspector.get_unique_constraints("file")
    name_constraint = next(
        (c["name"] for c in constraints if set(c["column_names"]) == {"name"}),
        None,
    )

    # Ensure that the new key name is not already in use
    if any(c["name"] == "file_name_user_id_key" for c in constraints):
        raise RuntimeError(
            "Upgrade aborted: The unique constraint 'file_name_user_id_key' already exists."
        )

    if is_sqlite:
        # SQLite: Recreate table with composite constraint
        op.create_table(
            "file_new",
            *file_table_columns,
            sa.UniqueConstraint("name", "user_id", name="file_name_user_id_key"),
        )

        # Verify new table was created before proceeding
        if not inspector.has_table("file_new"):
            raise RuntimeError("New table creation failed")

        op.execute(sa.text("""
            INSERT INTO file_new (
                id, user_id, name, path, size, provider, created_at, updated_at
            )
            SELECT id, user_id, name, path, size, provider, created_at, updated_at
            FROM file
        """))

        # Verify row counts match after data copy
        original_count = conn.execute(sa.text("SELECT COUNT(*) FROM file")).scalar()
        new_count = conn.execute(sa.text("SELECT COUNT(*) FROM file_new")).scalar()
        if original_count != new_count:
            raise RuntimeError("Data copy verification failed")

        op.drop_table("file")
        op.rename_table("file_new", "file")
    else:
        # PostgreSQL: Drop old unique, add new composite
        with op.batch_alter_table("file") as batch_op:
            if name_constraint:
                batch_op.drop_constraint(name_constraint, type_="unique")
            batch_op.create_unique_constraint("file_name_user_id_key", ["name", "user_id"])


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
        raise RuntimeError(
            f"Downgrade aborted: Duplicate file names exist across users: {duplicate_names}. "
            f"To resolve, rename conflicting files or manually handle the migration."
        )

    if is_sqlite:
        # SQLite: Recreate table with single column constraint
        op.create_table(
            "file_new",
            *file_table_columns,
            sa.UniqueConstraint("name", name="file_name_key"),
        )

        # Verify new table was created before proceeding
        if not inspector.has_table("file_new"):
            raise RuntimeError("New table creation failed")

        op.execute(sa.text("""
            INSERT INTO file_new (
                id, user_id, name, path, size, provider, created_at, updated_at
            )
            SELECT id, user_id, name, path, size, provider, created_at, updated_at
            FROM file
        """))

        # Verify row counts match after data copy
        original_count = conn.execute(sa.text("SELECT COUNT(*) FROM file")).scalar()
        new_count = conn.execute(sa.text("SELECT COUNT(*) FROM file_new")).scalar()
        if original_count != new_count:
            raise RuntimeError("Data copy verification failed")

        op.drop_table("file")
        op.rename_table("file_new", "file")
    else:
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
