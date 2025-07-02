"""Rename default folder

Revision ID: d9a6ea21edcd
Revises: 66f72f04a1de
Create Date: 2025-07-02 09:42:46.891585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'd9a6ea21edcd'
down_revision: Union[str, None] = '66f72f04a1de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Check if the folder table exists
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    
    if "folder" not in table_names:
        # If folder table doesn't exist, skip this migration
        return
    
    # Query for folders named "My Projects" and "Starter Project"
    # We need to check for each user separately due to the unique constraint
    my_projects_query = sa.text("""
        SELECT DISTINCT user_id 
        FROM folder 
        WHERE name = 'My Projects'
    """)
    
    starter_project_query = sa.text("""
        SELECT DISTINCT user_id 
        FROM folder 
        WHERE name = 'Starter Project'
    """)
    
    # Get users who have "My Projects" folder
    my_projects_users = conn.execute(my_projects_query).fetchall()
    
    # Get users who have "Starter Project" folder
    starter_project_users = set(row[0] for row in conn.execute(starter_project_query).fetchall())
    
    # For each user who has "My Projects" but not "Starter Project", rename the folder
    for user_row in my_projects_users:
        user_id = user_row[0]
        
        # Skip if this user already has a "Starter Project" folder
        if user_id in starter_project_users:
            continue
            
        # Rename "My Projects" to "Starter Project" for this user
        update_query = sa.text("""
            UPDATE folder 
            SET name = 'Starter Project' 
            WHERE name = 'My Projects' AND user_id = :user_id
        """)
        
        conn.execute(update_query, {"user_id": user_id})


def downgrade() -> None:
    conn = op.get_bind()
    
    # Check if the folder table exists
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    
    if "folder" not in table_names:
        # If folder table doesn't exist, skip this migration
        return
    
    # Query for folders named "Starter Project" and "My Projects"
    starter_project_query = sa.text("""
        SELECT DISTINCT user_id 
        FROM folder 
        WHERE name = 'Starter Project'
    """)
    
    my_projects_query = sa.text("""
        SELECT DISTINCT user_id 
        FROM folder 
        WHERE name = 'My Projects'
    """)
    
    # Get users who have "Starter Project" folder
    starter_project_users = conn.execute(starter_project_query).fetchall()
    
    # Get users who have "My Projects" folder
    my_projects_users = set(row[0] for row in conn.execute(my_projects_query).fetchall())
    
    # For each user who has "Starter Project" but not "My Projects", rename back to "My Projects"
    for user_row in starter_project_users:
        user_id = user_row[0]
        
        # Skip if this user already has a "My Projects" folder
        if user_id in my_projects_users:
            continue
            
        # Rename "Starter Project" back to "My Projects" for this user
        update_query = sa.text("""
            UPDATE folder 
            SET name = 'My Projects' 
            WHERE name = 'Starter Project' AND user_id = :user_id
        """)
        
        conn.execute(update_query, {"user_id": user_id})
