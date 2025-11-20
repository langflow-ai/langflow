"""Folder-scoped flow uniqueness

Revision ID: 20251120000000
Revises: 449cd6ba5a2e
Create Date: 2025-11-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "20251120000000"
down_revision: Union[str, None] = "449cd6ba5a2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Change flow name and endpoint_name uniqueness from global per-user
    to folder-scoped (unique within folder per user).
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    constraints_names = [constraint["name"] for constraint in inspector.get_unique_constraints("flow")]

    with op.batch_alter_table("flow", schema=None) as batch_op:
        # Drop old constraints if they exist
        if "unique_flow_name" in constraints_names:
            batch_op.drop_constraint("unique_flow_name", type_="unique")
        if "unique_flow_endpoint_name" in constraints_names:
            batch_op.drop_constraint("unique_flow_endpoint_name", type_="unique")

        # Create new folder-scoped constraints
        batch_op.create_unique_constraint("unique_flow_name", ["user_id", "folder_id", "name"])
        batch_op.create_unique_constraint("unique_flow_endpoint_name", ["user_id", "folder_id", "endpoint_name"])


def downgrade() -> None:
    """
    Revert to global per-user uniqueness for flow names and endpoint names.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)  # type: ignore
    constraints_names = [constraint["name"] for constraint in inspector.get_unique_constraints("flow")]

    with op.batch_alter_table("flow", schema=None) as batch_op:
        # Drop folder-scoped constraints if they exist
        if "unique_flow_name" in constraints_names:
            batch_op.drop_constraint("unique_flow_name", type_="unique")
        if "unique_flow_endpoint_name" in constraints_names:
            batch_op.drop_constraint("unique_flow_endpoint_name", type_="unique")

        # Recreate old global constraints
        batch_op.create_unique_constraint("unique_flow_name", ["user_id", "name"])
        batch_op.create_unique_constraint("unique_flow_endpoint_name", ["user_id", "endpoint_name"])
