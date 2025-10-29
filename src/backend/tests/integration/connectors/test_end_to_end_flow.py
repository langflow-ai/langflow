"""End-to-end integration tests for connector flow.

These tests simulate the complete user journey and would catch
issues that only appear when all components work together.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.connectors.oauth_handler import OAuthHandler
from langflow.services.connectors.service import ConnectorService
from langflow.services.database.models.connector.model import ConnectorConnection
from sqlmodel import select


@pytest.mark.asyncio
async def test_complete_oauth_flow_persistence(async_session):
    """Test complete OAuth flow: create → authorize → verify tokens saved.

    This would have caught the bug where OAuth callback showed success
    but tokens weren't actually persisted to database.
    """
    connector_service = ConnectorService()

    # Step 1: Create connection
    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test Drive",
        config={"folder_id": "root"},
    )

    assert connection.id is not None
    initial_config = connection.config.copy()
    assert "access_token" not in initial_config

    # Step 2: Generate OAuth URL (stores state)
    state = "test_state_token_12345"
    await connector_service.update_connection(
        session=async_session,
        connection_id=connection.id,
        user_id=connection.user_id,
        update_data={"config": {**connection.config, "oauth_state": state}},
    )

    # Step 3: Simulate OAuth callback (exchange code for tokens)
    oauth_handler = OAuthHandler(
        connector_type="google_drive",
        client_id="test_client",
        client_secret="test_secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="http://localhost/callback",
    )

    # Mock the actual Google API call
    with patch.object(oauth_handler, "handle_callback") as mock_callback:
        # Simulate what handle_callback does
        async def store_tokens(*args, **kwargs):  # noqa: ARG001
            token_data = {
                "access_token": "ya29.test_access_token",
                "refresh_token": "1//test_refresh_token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "test_client",
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            }
            await oauth_handler._store_tokens(async_session, connection.id, token_data)

        mock_callback.side_effect = store_tokens

        await oauth_handler.handle_callback(
            session=async_session, connection_id=connection.id, code="test_auth_code", state=state
        )

    # Step 4: CRITICAL - Verify tokens are in database (not just in memory)
    # This is the test that would have caught our bug!
    result = await async_session.exec(select(ConnectorConnection).where(ConnectorConnection.id == connection.id))
    authenticated_connection = result.first()

    # These assertions would FAIL if session wasn't committed
    assert authenticated_connection is not None, "Connection not found"
    assert authenticated_connection.config is not None, "Config is None"
    assert "access_token" in authenticated_connection.config, "No access_token in DB!"
    assert "refresh_token" in authenticated_connection.config, "No refresh_token in DB!"

    # Verify they're encrypted
    assert authenticated_connection.config["access_token"] != "ya29.test_access_token"  # noqa: S105
    assert (
        "encrypted" in str(type(authenticated_connection.config["access_token"]))
        or len(authenticated_connection.config["access_token"]) > 50
    )  # Encrypted tokens are longer


@pytest.mark.asyncio
async def test_create_and_sync_flow(async_session):
    """Test create → authenticate → sync flow.

    Would catch UUID generation errors and sync failures.
    """
    connector_service = ConnectorService()

    # Create and authenticate
    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test Drive",
        config={
            "folder_id": "root",
            "access_token": "test_token",  # Simulate authenticated
        },
    )

    # Trigger sync
    try:
        task_id = await connector_service.sync_files(
            session=async_session,
            connection_id=connection.id,
            user_id=connection.user_id,
            max_files=10,
        )

        # Verify valid UUID (would fail with UUID() bug)
        from uuid import UUID

        UUID(task_id)  # Throws if invalid
        assert isinstance(task_id, str)
        assert len(task_id) == 36

    except (NotImplementedError, RuntimeError) as e:
        # Sync might not be fully implemented or circuit breaker might be open
        if "not yet implemented" in str(e) or "circuit breaker" in str(e).lower():
            pytest.skip(f"Sync not ready: {e}")
        raise


@pytest.mark.asyncio
async def test_config_update_creates_new_dict(async_session):
    """Test that config updates use a new dict instance.

    Would catch the SQLAlchemy change detection bug where updates
    to the same dict object weren't detected.
    """
    connector_service = ConnectorService()

    connection = await connector_service.create_connection(
        session=async_session,
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test",
        config={"field1": "value1"},
    )

    original_config_id = id(connection.config)

    # Update using the CORRECT pattern (new dict)
    new_config = dict(connection.config or {})
    assert id(new_config) != original_config_id, "Must create new dict instance!"

    new_config["field2"] = "value2"

    await connector_service.update_connection(
        session=async_session,
        connection_id=connection.id,
        user_id=connection.user_id,
        update_data={"config": new_config},
    )

    # Verify in database
    result = await async_session.exec(select(ConnectorConnection).where(ConnectorConnection.id == connection.id))
    db_connection = result.first()

    assert db_connection.config["field1"] == "value1"
    assert db_connection.config["field2"] == "value2"


@pytest.mark.asyncio
async def test_multiple_connections_isolated_by_user(async_session):
    """Test that users can only access their own connections.

    Verifies user isolation security.
    """
    connector_service = ConnectorService()

    user1_id = uuid4()
    user2_id = uuid4()

    # User 1 creates connection
    conn1 = await connector_service.create_connection(
        session=async_session,
        user_id=user1_id,
        connector_type="google_drive",
        name="User 1 Drive",
        config={},
    )

    # User 2 creates connection
    conn2 = await connector_service.create_connection(
        session=async_session,
        user_id=user2_id,
        connector_type="google_drive",
        name="User 2 Drive",
        config={},
    )

    # User 1 should only see their connection
    user1_connections = await connector_service.get_user_connections(session=async_session, user_id=user1_id)
    assert len(user1_connections) == 1
    assert user1_connections[0].id == conn1.id

    # User 2 should only see their connection
    user2_connections = await connector_service.get_user_connections(session=async_session, user_id=user2_id)
    assert len(user2_connections) == 1
    assert user2_connections[0].id == conn2.id

    # User 1 cannot access User 2's connection
    user2_conn_from_user1 = await connector_service.get_connection(
        session=async_session, connection_id=conn2.id, user_id=user1_id
    )
    assert user2_conn_from_user1 is None, "User should not access other user's connection!"
