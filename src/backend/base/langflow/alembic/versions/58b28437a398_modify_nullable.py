"""Modify nullable

Revision ID: 58b28437a398
Revises: 4e5980a44eaa
Create Date: 2024-04-13 10:57:23.061709

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from loguru import logger
from sqlalchemy.engine.reflection import Inspector

down_revision: Union[str, None] = "4e5980a44eaa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Revision identifiers, used by Alembic.
revision = "58b28437a398"
down_revision = "4e5980a44eaa"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = ["apikey", "variable"]  # List of tables to modify

    for table_name in tables:
        modify_nullable(conn, inspector, table_name, upgrade=True)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = ["apikey", "variable"]  # List of tables to revert

    for table_name in tables:
        modify_nullable(conn, inspector, table_name, upgrade=False)


def modify_nullable(conn, inspector, table_name, upgrade=True):
    columns = inspector.get_columns(table_name)
    nullable_changes = {"apikey": {"created_at": False}, "variable": {"created_at": True, "updated_at": True}}

    if table_name in columns:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            for column_name, nullable_setting in nullable_changes.get(table_name, {}).items():
                column_info = next((col for col in columns if col["name"] == column_name), None)
                if column_info:
                    current_nullable = column_info["nullable"]
                    target_nullable = nullable_setting if upgrade else not nullable_setting

                    if current_nullable != target_nullable:
                        batch_op.alter_column(
                            column_name, existing_type=sa.DateTime(timezone=True), nullable=target_nullable
                        )
                    else:
                        logger.info(
                            f"Column '{column_name}' in table '{table_name}' already has nullable={target_nullable}"
                        )
                else:
                    logger.warning(f"Column '{column_name}' not found in table '{table_name}'")
