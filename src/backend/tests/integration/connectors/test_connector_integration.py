"""Comprehensive integration tests for the connector system.

This test suite focuses on end-to-end integration testing with minimal mocking,
using real database operations to verify the complete connector workflow.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.connectors.service import ConnectorService
from langflow.services.database.models.connector import ConnectorOAuthToken, ConnectorSyncLog
from langflow.services.database.models.connector.crud import create_oauth_token, create_sync_log, update_oauth_token
from langflow.services.deps import get_db_service, session_scope
from sqlalchemy.exc import IntegrityError
from sqlmodel import select


@pytest.fixture
async def connector_service():
    """Provide a ConnectorService instance."""
    return ConnectorService()


@pytest.fixture
async def test_user_id():
    """Provide a test user ID."""
    return uuid4()


@pytest.fixture
async def second_user_id():
    """Provide a second test user ID for multi-user tests."""
    return uuid4()


@pytest.fixture
async def db_session(client):  # noqa: ARG001
    """Provide a database session for integration tests."""
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        yield session


@pytest.mark.usefixtures("client")
class TestConnectorCreationAndRetrieval:
    """Test creating and retrieving connector connections."""

    async def test_create_connection_persists_to_database(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that creating a connection actually persists to the database."""
        async with session_scope() as session:
            # Create connection
            connection = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Test Drive Connection",
                config={"folder_id": "root", "include_shared": True},
            )

            # Verify connection was created with correct data
            assert connection.id is not None
            assert connection.user_id == test_user_id
            assert connection.connector_type == "google_drive"
            assert connection.name == "Test Drive Connection"
            assert connection.config["folder_id"] == "root"
            assert connection.config["include_shared"] is True
            assert connection.is_active is True
            assert connection.created_at is not None
            assert connection.updated_at is not None

            # Verify it can be retrieved from database
            retrieved = await connector_service.get_connection(
                session=session,
                connection_id=connection.id,
                user_id=test_user_id,
            )

            assert retrieved is not None
            assert retrieved.id == connection.id
            assert retrieved.name == "Test Drive Connection"
            assert retrieved.config == connection.config

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=connection.id,
                user_id=test_user_id,
            )

    async def test_create_connection_with_knowledge_base_id(
        self,
        connector_service,
        test_user_id,
    ):
        """Test creating a connection associated with a knowledge base."""
        kb_id = "kb_test_123"

        async with session_scope() as session:
            connection = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="onedrive",
                name="OneDrive KB Connection",
                config={"folder": "Documents"},
                knowledge_base_id=kb_id,
            )

            assert connection.knowledge_base_id == kb_id

            # Verify filtering by knowledge base
            connections = await connector_service.get_user_connections(
                session=session,
                user_id=test_user_id,
                knowledge_base_id=kb_id,
            )

            assert len(connections) == 1
            assert connections[0].id == connection.id

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=connection.id,
                user_id=test_user_id,
            )

    async def test_get_nonexistent_connection_returns_none(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that getting a non-existent connection returns None."""
        async with session_scope() as session:
            result = await connector_service.get_connection(
                session=session,
                connection_id=uuid4(),
                user_id=test_user_id,
            )

            assert result is None


@pytest.mark.usefixtures("client")
class TestMultiUserIsolation:
    """Test that users can only access their own connections."""

    async def test_users_have_isolated_connections(
        self,
        connector_service,
        test_user_id,
        second_user_id,
    ):
        """Test that each user only sees their own connections."""
        async with session_scope() as session:
            # User 1 creates connections
            conn1 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="User 1 Drive",
                config={},
            )

            # User 2 creates connections
            conn2 = await connector_service.create_connection(
                session=session,
                user_id=second_user_id,
                connector_type="google_drive",
                name="User 2 Drive",
                config={},
            )

            # User 1 should only see their connections
            user1_connections = await connector_service.get_user_connections(
                session=session,
                user_id=test_user_id,
            )
            assert len(user1_connections) == 1
            assert user1_connections[0].id == conn1.id

            # User 2 should only see their connections
            user2_connections = await connector_service.get_user_connections(
                session=session,
                user_id=second_user_id,
            )
            assert len(user2_connections) == 1
            assert user2_connections[0].id == conn2.id

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn1.id,
                user_id=test_user_id,
            )
            await connector_service.delete_connection(
                session=session,
                connection_id=conn2.id,
                user_id=second_user_id,
            )

    async def test_user_cannot_access_other_user_connection(
        self,
        connector_service,
        test_user_id,
        second_user_id,
    ):
        """Test that a user cannot access another user's connection."""
        async with session_scope() as session:
            # User 1 creates a connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="User 1 Private",
                config={},
            )

            # User 2 tries to access User 1's connection
            result = await connector_service.get_connection(
                session=session,
                connection_id=conn.id,
                user_id=second_user_id,
            )

            assert result is None

            # User 2 tries to delete User 1's connection
            deleted = await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=second_user_id,
            )

            assert deleted is False

            # Verify connection still exists for User 1
            still_exists = await connector_service.get_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )
            assert still_exists is not None

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

    async def test_user_cannot_update_other_user_connection(
        self,
        connector_service,
        test_user_id,
        second_user_id,
    ):
        """Test that a user cannot update another user's connection."""
        async with session_scope() as session:
            # User 1 creates a connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Original Name",
                config={},
            )

            # User 2 tries to update User 1's connection
            result = await connector_service.update_connection(
                session=session,
                connection_id=conn.id,
                user_id=second_user_id,
                update_data={"name": "Hacked Name"},
            )

            assert result is None

            # Verify connection name unchanged
            unchanged = await connector_service.get_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )
            assert unchanged.name == "Original Name"

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )


@pytest.mark.usefixtures("client")
class TestConnectionUpdates:
    """Test updating connector connections."""

    async def test_update_connection_name(
        self,
        connector_service,
        test_user_id,
    ):
        """Test updating a connection's name."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Original Name",
                config={},
            )

            # Update name
            updated = await connector_service.update_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
                update_data={"name": "Updated Name"},
            )

            assert updated is not None
            assert updated.name == "Updated Name"
            assert updated.id == conn.id

            # Verify persistence
            retrieved = await connector_service.get_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )
            assert retrieved.name == "Updated Name"

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

    async def test_update_connection_config(
        self,
        connector_service,
        test_user_id,
    ):
        """Test updating a connection's configuration."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Test",
                config={"folder_id": "original"},
            )

            # Update config
            new_config = {"folder_id": "updated", "recursive": True}
            updated = await connector_service.update_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
                update_data={"config": new_config},
            )

            assert updated.config == new_config

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

    async def test_update_connection_is_active_status(
        self,
        connector_service,
        test_user_id,
    ):
        """Test deactivating and reactivating a connection."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Test",
                config={},
            )

            assert conn.is_active is True

            # Deactivate
            deactivated = await connector_service.update_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
                update_data={"is_active": False},
            )

            assert deactivated.is_active is False

            # Reactivate
            reactivated = await connector_service.update_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
                update_data={"is_active": True},
            )

            assert reactivated.is_active is True

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )


@pytest.mark.usefixtures("client")
class TestConnectionDeletion:
    """Test deleting connector connections."""

    async def test_delete_connection_removes_from_database(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that deleting a connection removes it from the database."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="To Delete",
                config={},
            )

            connection_id = conn.id

            # Verify it exists
            exists = await connector_service.get_connection(
                session=session,
                connection_id=connection_id,
                user_id=test_user_id,
            )
            assert exists is not None

            # Delete it
            deleted = await connector_service.delete_connection(
                session=session,
                connection_id=connection_id,
                user_id=test_user_id,
            )

            assert deleted is True

            # Verify it's gone
            not_found = await connector_service.get_connection(
                session=session,
                connection_id=connection_id,
                user_id=test_user_id,
            )
            assert not_found is None

    async def test_delete_nonexistent_connection_returns_false(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that deleting a non-existent connection returns False."""
        async with session_scope() as session:
            deleted = await connector_service.delete_connection(
                session=session,
                connection_id=uuid4(),
                user_id=test_user_id,
            )

            assert deleted is False


@pytest.mark.usefixtures("client")
class TestOAuthTokenStorage:
    """Test OAuth token storage and retrieval."""

    async def test_create_oauth_token_for_connection(
        self,
        connector_service,
        test_user_id,
    ):
        """Test creating and storing OAuth tokens."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="OAuth Test",
                config={},
            )

            # Create OAuth token
            token_data = {
                "connection_id": conn.id,
                "encrypted_access_token": "encrypted_access_token_123",
                "encrypted_refresh_token": "encrypted_refresh_token_456",
                "token_expiry": datetime.now(timezone.utc),
                "scopes": ["drive.readonly", "drive.metadata"],
                "provider_account_id": "user@example.com",
            }

            token = await create_oauth_token(session, token_data)

            # Verify token was created
            assert token.id is not None
            assert token.connection_id == conn.id
            assert token.encrypted_access_token == "encrypted_access_token_123"  # noqa: S105
            assert token.encrypted_refresh_token == "encrypted_refresh_token_456"  # noqa: S105
            assert token.scopes == ["drive.readonly", "drive.metadata"]
            assert token.provider_account_id == "user@example.com"

            # Verify we can query it
            stmt = select(ConnectorOAuthToken).where(ConnectorOAuthToken.connection_id == conn.id)
            result = await session.exec(stmt)
            retrieved_token = result.first()

            assert retrieved_token is not None
            assert retrieved_token.id == token.id

            # Cleanup
            await session.delete(token)
            await session.commit()
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

    async def test_update_existing_oauth_token(
        self,
        connector_service,
        test_user_id,
    ):
        """Test updating an existing OAuth token (token refresh)."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="OAuth Update Test",
                config={},
            )

            # Create initial token
            initial_token_data = {
                "connection_id": conn.id,
                "encrypted_access_token": "initial_access",
                "encrypted_refresh_token": "initial_refresh",
                "token_expiry": datetime.now(timezone.utc),
                "scopes": ["drive.readonly"],
            }

            initial_token = await create_oauth_token(session, initial_token_data)
            initial_id = initial_token.id

            # Update token (simulate refresh)
            updated_token_data = {
                "encrypted_access_token": "refreshed_access",
                "encrypted_refresh_token": "refreshed_refresh",
                "token_expiry": datetime.now(timezone.utc),
                "scopes": ["drive.readonly"],
            }

            updated_token = await update_oauth_token(session, conn.id, updated_token_data)

            # Should be the same token, just updated
            assert updated_token.id == initial_id
            assert updated_token.encrypted_access_token == "refreshed_access"  # noqa: S105
            assert updated_token.encrypted_refresh_token == "refreshed_refresh"  # noqa: S105

            # Verify only one token exists for the connection
            stmt = select(ConnectorOAuthToken).where(ConnectorOAuthToken.connection_id == conn.id)
            result = await session.exec(stmt)
            all_tokens = result.all()
            assert len(all_tokens) == 1

            # Cleanup
            await session.delete(updated_token)
            await session.commit()
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )


@pytest.mark.usefixtures("client")
class TestSyncLogCreation:
    """Test sync log creation and tracking."""

    async def test_create_sync_log(
        self,
        connector_service,
        test_user_id,
    ):
        """Test creating a sync log entry."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Sync Test",
                config={},
            )

            # Create sync log
            log_data = {
                "connection_id": conn.id,
                "sync_type": "full",
                "status": "pending",
                "files_processed": 0,
                "files_failed": 0,
            }

            sync_log = await create_sync_log(session, log_data)

            # Verify log was created
            assert sync_log.id is not None
            assert sync_log.connection_id == conn.id
            assert sync_log.sync_type == "full"
            assert sync_log.status == "pending"
            assert sync_log.files_processed == 0
            assert sync_log.started_at is not None

            # Cleanup
            await session.delete(sync_log)
            await session.commit()
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

    async def test_multiple_sync_logs_for_connection(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that a connection can have multiple sync logs."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Multi Sync Test",
                config={},
            )

            # Create multiple sync logs
            log1 = await create_sync_log(
                session,
                {
                    "connection_id": conn.id,
                    "sync_type": "full",
                    "status": "completed",
                    "files_processed": 50,
                    "files_failed": 0,
                },
            )

            log2 = await create_sync_log(
                session,
                {
                    "connection_id": conn.id,
                    "sync_type": "incremental",
                    "status": "completed",
                    "files_processed": 5,
                    "files_failed": 1,
                },
            )

            # Query all logs for this connection
            stmt = select(ConnectorSyncLog).where(ConnectorSyncLog.connection_id == conn.id)
            result = await session.exec(stmt)
            all_logs = result.all()

            assert len(all_logs) == 2
            assert {log.sync_type for log in all_logs} == {"full", "incremental"}

            # Cleanup
            await session.delete(log1)
            await session.delete(log2)
            await session.commit()
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

    async def test_sync_log_with_checkpoint_data(
        self,
        connector_service,
        test_user_id,
    ):
        """Test storing checkpoint data in sync logs."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Checkpoint Test",
                config={},
            )

            # Create sync log with checkpoint
            checkpoint_data = {
                "last_file_id": "file_123",
                "folder_stack": ["root", "folder1", "folder2"],
                "processed_count": 25,
            }

            log_data = {
                "connection_id": conn.id,
                "sync_type": "incremental",
                "status": "in_progress",
                "files_processed": 25,
                "files_failed": 0,
                "checkpoint": checkpoint_data,
                "page_token": "next_page_token_xyz",
            }

            sync_log = await create_sync_log(session, log_data)

            # Verify checkpoint data
            assert sync_log.checkpoint is not None
            assert sync_log.checkpoint["last_file_id"] == "file_123"
            assert sync_log.checkpoint["folder_stack"] == ["root", "folder1", "folder2"]
            assert sync_log.page_token == "next_page_token_xyz"  # noqa: S105

            # Cleanup
            await session.delete(sync_log)
            await session.commit()
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )


@pytest.mark.usefixtures("client")
class TestCascadingDeletes:
    """Test that deleting a connection cascades to related records."""

    async def test_deleting_connection_removes_oauth_token(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that deleting a connection also removes its OAuth token."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Cascade OAuth Test",
                config={},
            )

            # Create OAuth token
            token = await create_oauth_token(
                session,
                {
                    "connection_id": conn.id,
                    "encrypted_access_token": "test_token",
                    "encrypted_refresh_token": "test_refresh",
                },
            )

            token_id = token.id

            # Delete connection
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

            # Verify OAuth token is also deleted
            stmt = select(ConnectorOAuthToken).where(ConnectorOAuthToken.id == token_id)
            result = await session.exec(stmt)
            deleted_token = result.first()

            assert deleted_token is None

    async def test_deleting_connection_removes_sync_logs(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that deleting a connection also removes its sync logs."""
        async with session_scope() as session:
            # Create connection
            conn = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Cascade Sync Test",
                config={},
            )

            # Create sync logs
            log1 = await create_sync_log(
                session,
                {
                    "connection_id": conn.id,
                    "sync_type": "full",
                    "status": "completed",
                },
            )

            log2 = await create_sync_log(
                session,
                {
                    "connection_id": conn.id,
                    "sync_type": "incremental",
                    "status": "completed",
                },
            )

            log1_id = log1.id
            log2_id = log2.id

            # Delete connection
            await connector_service.delete_connection(
                session=session,
                connection_id=conn.id,
                user_id=test_user_id,
            )

            # Verify sync logs are also deleted
            stmt = select(ConnectorSyncLog).where(ConnectorSyncLog.id.in_([log1_id, log2_id]))
            result = await session.exec(stmt)
            remaining_logs = result.all()

            assert len(remaining_logs) == 0


@pytest.mark.usefixtures("client")
class TestKnowledgeBaseFiltering:
    """Test filtering connections by knowledge base."""

    async def test_get_connections_by_knowledge_base(
        self,
        connector_service,
        test_user_id,
    ):
        """Test retrieving connections filtered by knowledge base ID."""
        async with session_scope() as session:
            kb_id_1 = "kb_001"
            kb_id_2 = "kb_002"

            # Create connections for different knowledge bases
            conn1 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="KB1 Connection 1",
                config={},
                knowledge_base_id=kb_id_1,
            )

            conn2 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="onedrive",
                name="KB1 Connection 2",
                config={},
                knowledge_base_id=kb_id_1,
            )

            conn3 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="KB2 Connection",
                config={},
                knowledge_base_id=kb_id_2,
            )

            conn4 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="No KB Connection",
                config={},
                knowledge_base_id=None,
            )

            # Get connections for KB1
            kb1_connections = await connector_service.get_user_connections(
                session=session,
                user_id=test_user_id,
                knowledge_base_id=kb_id_1,
            )

            assert len(kb1_connections) == 2
            assert {conn.id for conn in kb1_connections} == {conn1.id, conn2.id}

            # Get connections for KB2
            kb2_connections = await connector_service.get_user_connections(
                session=session,
                user_id=test_user_id,
                knowledge_base_id=kb_id_2,
            )

            assert len(kb2_connections) == 1
            assert kb2_connections[0].id == conn3.id

            # Get all connections (no filter)
            all_connections = await connector_service.get_user_connections(
                session=session,
                user_id=test_user_id,
            )

            assert len(all_connections) == 4

            # Cleanup
            for conn in [conn1, conn2, conn3, conn4]:
                await connector_service.delete_connection(
                    session=session,
                    connection_id=conn.id,
                    user_id=test_user_id,
                )


@pytest.mark.usefixtures("client")
class TestErrorHandling:
    """Test error handling in various scenarios."""

    async def test_update_nonexistent_connection_returns_none(
        self,
        connector_service,
        test_user_id,
    ):
        """Test updating a non-existent connection returns None."""
        async with session_scope() as session:
            result = await connector_service.update_connection(
                session=session,
                connection_id=uuid4(),
                user_id=test_user_id,
                update_data={"name": "Updated"},
            )

            assert result is None

    async def test_create_duplicate_connection_name_same_kb(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that unique constraint prevents duplicate connections."""
        kb_id = "kb_duplicate_test"

        # Create first connection
        async with session_scope() as session:
            conn1 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Duplicate Name",
                config={},
                knowledge_base_id=kb_id,
            )
            conn1_id = conn1.id

        # Try to create duplicate in a separate session
        # This should raise an exception due to unique constraint
        with pytest.raises(IntegrityError):
            async with session_scope() as session:
                await connector_service.create_connection(
                    session=session,
                    user_id=test_user_id,
                    connector_type="google_drive",
                    name="Duplicate Name",
                    config={},
                    knowledge_base_id=kb_id,
                )

        # Cleanup in fresh session
        async with session_scope() as session:
            await connector_service.delete_connection(
                session=session,
                connection_id=conn1_id,
                user_id=test_user_id,
            )

    async def test_same_name_different_kb_allowed(
        self,
        connector_service,
        test_user_id,
    ):
        """Test that same name is allowed for different knowledge bases."""
        async with session_scope() as session:
            # Create connections with same name but different KBs
            conn1 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Same Name",
                config={},
                knowledge_base_id="kb_001",
            )

            conn2 = await connector_service.create_connection(
                session=session,
                user_id=test_user_id,
                connector_type="google_drive",
                name="Same Name",
                config={},
                knowledge_base_id="kb_002",
            )

            # Both should exist
            assert conn1.id != conn2.id

            # Cleanup
            await connector_service.delete_connection(
                session=session,
                connection_id=conn1.id,
                user_id=test_user_id,
            )
            await connector_service.delete_connection(
                session=session,
                connection_id=conn2.id,
                user_id=test_user_id,
            )
