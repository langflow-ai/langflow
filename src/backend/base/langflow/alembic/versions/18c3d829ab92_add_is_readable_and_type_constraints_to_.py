"""Add is_readable and type constraints to variable

Revision ID: 18c3d829ab92
Revises: 1a110b568907
Create Date: 2024-04-08 11:14:34.096838

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql import column, func, table

revision: str = "18c3d829ab92"
down_revision: Union[str, None] = "1a110b568907"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    # Checking if the 'variable' table exists to avoid errors in case it doesn't
    if "variable" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("variable")]
        category_type = sa.Enum("GENERIC", "CREDENTIAL", "PROMPT", name="variablecategories")
        # Add 'category' column if it does not exist
        if "category" not in columns:
            op.add_column("variable", sa.Column("category", category_type, nullable=True))

        # Add 'is_readable' column if it does not exist
        if "is_readable" not in columns:
            op.add_column("variable", sa.Column("is_readable", sa.Boolean(), nullable=True))

        # Migrate data from 'type' to 'category' if 'type' exists and 'category' has been successfully added
        if "type" in columns and "category" in columns:
            variable_temp = table(
                "variable",
                column("type", sa.String),  # Assuming 'type' is of type String, adjust if necessary
                column("category", category_type),
            )
            # Type values might be different from category values
            # so we need to maybe uppercase them or something
            op.execute(variable_temp.update().values(category=func.upper(variable_temp.c.type)))
            # Drop 'type' column after migration
        if "type" in columns:
            op.drop_column("variable", "type")


def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    if "variable" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("variable")]

        # Add 'type' column if it does not exist (for downgrade)
        if "type" not in columns:
            op.add_column("variable", sa.Column("type", sa.String(), nullable=True))

        # Drop 'is_readable' column if it exists
        if "is_readable" in columns:
            op.drop_column("variable", "is_readable")

        # Migrate data from 'category' to 'type' if 'category' exists and 'type' has been successfully added
        if "category" in columns and "type" in columns:
            # category is of type Enum
            # as can be seen here:
            category_type = sa.Enum("GENERIC", "CREDENTIAL", "PROMPT", name="variablecategories")
            # op.add_column("variable", sa.Column("category", category_type, nullable=True))
            variable_temp = table(
                "variable",
                column("category", category_type),
                column("type", sa.String),
            )

            op.execute(variable_temp.update().values(type=variable_temp.c.category))

            # Drop 'category' column after migration
            op.drop_column("variable", "category")
