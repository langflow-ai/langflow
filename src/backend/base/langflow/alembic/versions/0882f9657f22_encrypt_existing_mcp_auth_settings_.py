"""Encrypt existing MCP auth_settings credentials

Revision ID: 0882f9657f22
Revises: 1cb603706752
Create Date: 2025-08-21 20:11:26.504681

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '0882f9657f22'
down_revision: Union[str, None] = '1cb603706752'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Encrypt sensitive fields in existing auth_settings data."""
    conn = op.get_bind()
    
    # Import encryption utilities
    try:
        from langflow.services.auth.mcp_encryption import encrypt_auth_settings
        from langflow.services.deps import get_settings_service
        
        # Check if the folder table exists
        inspector = sa.inspect(conn)
        if 'folder' not in inspector.get_table_names():
            return
            
        # Query all folders with auth_settings
        result = conn.execute(
            sa.text("SELECT id, auth_settings FROM folder WHERE auth_settings IS NOT NULL")
        )
        
        # Encrypt auth_settings for each folder
        for row in result:
            folder_id = row.id
            auth_settings = row.auth_settings
            
            if auth_settings:
                try:
                    # Parse JSON if it's a string
                    if isinstance(auth_settings, str):
                        auth_settings_dict = json.loads(auth_settings)
                    else:
                        auth_settings_dict = auth_settings
                    
                    # Encrypt sensitive fields
                    encrypted_settings = encrypt_auth_settings(auth_settings_dict)
                    
                    # Update the record with encrypted data
                    if encrypted_settings:
                        conn.execute(
                            sa.text("UPDATE folder SET auth_settings = :auth_settings WHERE id = :id"),
                            {"auth_settings": json.dumps(encrypted_settings), "id": folder_id}
                        )
                except Exception as e:
                    # Log the error but continue with other records
                    print(f"Warning: Failed to encrypt auth_settings for folder {folder_id}: {e}")
                    
    except ImportError as e:
        # If encryption utilities are not available, skip the migration
        print(f"Warning: Encryption utilities not available, skipping encryption migration: {e}")


def downgrade() -> None:
    """Decrypt sensitive fields in auth_settings data (for rollback)."""
    conn = op.get_bind()
    
    # Import decryption utilities
    try:
        from langflow.services.auth.mcp_encryption import decrypt_auth_settings
        from langflow.services.deps import get_settings_service
        
        # Check if the folder table exists
        inspector = sa.inspect(conn)
        if 'folder' not in inspector.get_table_names():
            return
            
        # Query all folders with auth_settings
        result = conn.execute(
            sa.text("SELECT id, auth_settings FROM folder WHERE auth_settings IS NOT NULL")
        )
        
        # Decrypt auth_settings for each folder
        for row in result:
            folder_id = row.id
            auth_settings = row.auth_settings
            
            if auth_settings:
                try:
                    # Parse JSON if it's a string
                    if isinstance(auth_settings, str):
                        auth_settings_dict = json.loads(auth_settings)
                    else:
                        auth_settings_dict = auth_settings
                    
                    # Decrypt sensitive fields
                    decrypted_settings = decrypt_auth_settings(auth_settings_dict)
                    
                    # Update the record with decrypted data
                    if decrypted_settings:
                        conn.execute(
                            sa.text("UPDATE folder SET auth_settings = :auth_settings WHERE id = :id"),
                            {"auth_settings": json.dumps(decrypted_settings), "id": folder_id}
                        )
                except Exception as e:
                    # Log the error but continue with other records
                    print(f"Warning: Failed to decrypt auth_settings for folder {folder_id}: {e}")
                    
    except ImportError as e:
        # If decryption utilities are not available, skip the migration
        print(f"Warning: Decryption utilities not available, skipping decryption migration: {e}")
