"""Integration tests for OAuth token persistence.

These tests use a real database to verify tokens are actually saved,
catching issues like session commit problems and SQLAlchemy change detection.
"""

from uuid import uuid4

import pytest
from langflow.services.connectors.oauth_handler import OAuthHandler
from langflow.services.connectors.service import ConnectorService
from langflow.services.database.models.connector.model import ConnectorConnection
from sqlmodel import select


@pytest.mark.asyncio
async def test_oauth_tokens_persist_to_database(async_session):
    """Test that OAuth tokens actually persist to database after callback.

    This would have caught the session commit bug where tokens were
    'stored' but not actually persisted.
    """
    # Create a real connection in database
    connector_service = ConnectorService()
    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test Connection",
        config={"folder_id": "root"},
    )

    # Simulate OAuth token storage
    oauth_handler = OAuthHandler(
        connector_type="google_drive",
        client_id="test_client",
        client_secret="test_secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="http://localhost/callback",
    )

    # Store tokens
    token_data = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }

    await oauth_handler._store_tokens(async_session, connection.id, token_data)

    # CRITICAL: Query database again to verify persistence
    result = await async_session.exec(select(ConnectorConnection).where(ConnectorConnection.id == connection.id))
    saved_connection = result.first()

    # Verify tokens are actually in the database
    assert saved_connection is not None, "Connection not found after token storage"
    assert saved_connection.config is not None, "Config is None"
    assert "access_token" in saved_connection.config, "access_token not in config"
    assert "refresh_token" in saved_connection.config, "refresh_token not in config"

    # Verify they're encrypted (not plain text)
    assert saved_connection.config["access_token"] != "test_access_token"  # noqa: S105
    assert saved_connection.config["refresh_token"] != "test_refresh_token"  # noqa: S105


@pytest.mark.asyncio
async def test_json_field_updates_are_detected(async_session):
    """Test that JSON field changes are properly detected by SQLAlchemy.

    This would have caught the issue where config updates weren't
    persisting due to SQLAlchemy not detecting the change.
    """
    connector_service = ConnectorService()

    # Create connection
    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test Connection",
        config={"folder_id": "root", "recursive": False},
    )

    # Update config (this is where the bug was)
    new_config = dict(connection.config or {})  # Must create NEW dict
    new_config["access_token"] = "encrypted_token_123"  # noqa: S105
    new_config["new_field"] = "new_value"

    await connector_service.update_connection(
        session=async_session,
        connection_id=connection.id,
        user_id=connection.user_id,
        update_data={"config": new_config},
    )

    # Re-query from database to verify persistence
    result = await async_session.exec(select(ConnectorConnection).where(ConnectorConnection.id == connection.id))
    updated_connection = result.first()

    # Verify changes persisted
    assert updated_connection.config["access_token"] == "encrypted_token_123"  # noqa: S105
    assert updated_connection.config["new_field"] == "new_value"
    assert updated_connection.config["folder_id"] == "root"  # Original field preserved


@pytest.mark.asyncio
async def test_sync_files_returns_valid_uuid(async_session):
    """Test that sync_files returns a valid UUID string.

    This would have caught the UUID() vs uuid4() bug.
    """
    connector_service = ConnectorService()

    # Create authenticated connection
    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test Connection",
        config={"folder_id": "root", "access_token": "test_token"},
    )

    try:
        # Call sync_files
        task_id = await connector_service.sync_files(
            session=async_session,
            connection_id=connection.id,
            user_id=connection.user_id,
            max_files=10,
        )

        # Verify it's a valid UUID string
        from uuid import UUID

        parsed_uuid = UUID(task_id)  # This would fail if task_id is invalid
        assert str(parsed_uuid) == task_id
        assert len(task_id) == 36  # Standard UUID format

    except NotImplementedError:
        # sync_files might not be fully implemented yet
        pytest.skip("sync_files not fully implemented")


@pytest.mark.asyncio
async def test_connection_update_commits_to_database(async_session):
    """Test that connection updates are committed and queryable.

    This verifies the session commit is actually happening.
    """
    connector_service = ConnectorService()

    # Create connection
    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Original Name",
        config={},
    )

    # Update it
    await connector_service.update_connection(
        session=async_session,
        connection_id=connection.id,
        user_id=connection.user_id,
        update_data={"name": "Updated Name"},
    )

    # Close and reopen session to force read from database
    await async_session.close()

    # Re-query with fresh session (would fail if commit didn't happen)
    from langflow.services.database.models.connector import get_connection

    saved_connection = await get_connection(async_session, connection.id)

    assert saved_connection is not None
    assert saved_connection.name == "Updated Name"
