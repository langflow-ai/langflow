"""Make variable.category column nullable.

Revision ID: manual_fix_variable_category
Revises: 4d0cfe25d5e0
Create Date: 2025-10-16 13:05:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import VARCHAR

# revision identifiers, used by Alembic.
revision: str = "manual_fix_variable_category"
down_revision: str | None = "4d0cfe25d5e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN directly, so we need to use a workaround
    # Create a new table with the desired schema
    with op.batch_alter_table("variable") as batch_op:
        batch_op.alter_column("category", existing_type=VARCHAR(), nullable=True)


def downgrade() -> None:
    # Revert the change
    with op.batch_alter_table("variable") as batch_op:
        batch_op.alter_column("category", existing_type=VARCHAR(), nullable=False)
