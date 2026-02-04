"""update_memory_component_path_from_helpers_to_models_agents

Revision ID: bcbbf8c17c25
Revises: d37bc4322900
Create Date: 2025-10-03 00:44:35.536421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'bcbbf8c17c25'
down_revision: Union[str, None] = 'd37bc4322900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Check if the flow table exists
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    
    if "flow" not in table_names:
        # If flow table doesn't exist, skip this migration
        return
    
    # Update memory component path from helpers to models_agents in flow data
    update_query = sa.text("""
        UPDATE flow
        SET data = REPLACE(data, 'lfx.components.helpers.memory', 'lfx.components.models_agents.memory'),
            updated_at = CURRENT_TIMESTAMP
        WHERE data LIKE '%lfx.components.helpers.memory%'
    """)
    
    result = conn.execute(update_query)
    
    # Log the number of updated flows
    if result.rowcount > 0:
        print(f"Updated {result.rowcount} flows with new memory component path")


def downgrade() -> None:
    conn = op.get_bind()
    
    # Check if the flow table exists
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    
    if "flow" not in table_names:
        # If flow table doesn't exist, skip this migration
        return
    
    # Revert memory component path from models_agents back to helpers
    update_query = sa.text("""
        UPDATE flow
        SET data = REPLACE(data, 'lfx.components.models_agents.memory', 'lfx.components.helpers.memory'),
            updated_at = CURRENT_TIMESTAMP
        WHERE data LIKE '%lfx.components.models_agents.memory%'
    """)
    
    result = conn.execute(update_query)
    
    # Log the number of reverted flows
    if result.rowcount > 0:
        print(f"Reverted {result.rowcount} flows to old memory component path")
