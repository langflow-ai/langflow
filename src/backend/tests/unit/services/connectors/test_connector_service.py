from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.connectors.service import ConnectorService
from langflow.services.database.models.connector import ConnectorConnection


class TestConnectorServiceCreation:
    """Test creating ConnectorService."""

    def test_connector_service_creation(self):
        """Test creating ConnectorService."""
        service = ConnectorService()
        assert service is not None
        assert hasattr(service, "create_connection")
        assert hasattr(service, "get_connection")
        assert hasattr(service, "delete_connection")
        assert hasattr(service, "update_connection")
        assert hasattr(service, "get_user_connections")
        assert hasattr(service, "get_oauth_url")
        assert hasattr(service, "complete_oauth")
        assert hasattr(service, "sync_files")
        assert hasattr(service, "get_connector_instance")


class TestConnectorServiceMethods:
    """Test ConnectorService methods."""

    @pytest.mark.asyncio
    async def test_create_connection(self):
        """Test creating a connection."""
        service = ConnectorService()
        session = MagicMock()
        user_id = uuid4()

        # Mock the database create function
        expected_connection = ConnectorConnection(
            id=uuid4(),
            user_id=user_id,
            connector_type="google_drive",
            name="Test Drive",
            config={"folder": "root"},
            is_active=True,
        )

        with patch("langflow.services.connectors.service.db_create_connection", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = expected_connection

            result = await service.create_connection(
                session=session,
                user_id=user_id,
                connector_type="google_drive",
                name="Test Drive",
                config={"folder": "root"},
            )

            assert result == expected_connection
            mock_create.assert_called_once()

            # Verify the call arguments
            call_args = mock_create.call_args
            assert call_args[0][0] == session
            connection_data = call_args[0][1]
            assert connection_data["user_id"] == user_id
            assert connection_data["connector_type"] == "google_drive"
            assert connection_data["name"] == "Test Drive"

    @pytest.mark.asyncio
    async def test_get_connection(self):
        """Test getting a connection by ID."""
        service = ConnectorService()
        session = MagicMock()
        connection_id = uuid4()
        user_id = uuid4()

        expected_connection = ConnectorConnection(
            id=connection_id,
            user_id=user_id,
            connector_type="google_drive",
            name="Test Drive",
            config={},
            is_active=True,
        )

        with patch("langflow.services.connectors.service.db_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = expected_connection

            result = await service.get_connection(session=session, connection_id=connection_id, user_id=user_id)

            assert result == expected_connection
            mock_get.assert_called_once_with(session, connection_id, user_id=None)

    @pytest.mark.asyncio
    async def test_get_user_connections(self):
        """Test getting all connections for a user."""
        service = ConnectorService()
        session = MagicMock()
        user_id = uuid4()

        expected_connections = [
            ConnectorConnection(
                id=uuid4(), user_id=user_id, connector_type="google_drive", name="Drive 1", config={}, is_active=True
            ),
            ConnectorConnection(
                id=uuid4(), user_id=user_id, connector_type="onedrive", name="OneDrive 1", config={}, is_active=True
            ),
        ]

        with patch(
            "langflow.services.connectors.service.db_get_user_connections", new_callable=AsyncMock
        ) as mock_get_user:
            mock_get_user.return_value = expected_connections

            result = await service.get_user_connections(session=session, user_id=user_id)

            assert result == expected_connections
            assert len(result) == 2
            mock_get_user.assert_called_once_with(session, user_id, None)

    @pytest.mark.asyncio
    async def test_delete_connection(self):
        """Test deleting a connection."""
        service = ConnectorService()
        session = MagicMock()
        connection_id = uuid4()
        user_id = uuid4()

        with (
            patch("langflow.services.connectors.service.db_get_connection", new_callable=AsyncMock) as mock_get,
            patch("langflow.services.connectors.service.db_delete_connection", new_callable=AsyncMock) as mock_delete,
        ):
            # Mock the connection for validation
            mock_connection = ConnectorConnection(
                id=connection_id,
                user_id=user_id,
                connector_type="google_drive",
                name="Test",
                config={},
                is_active=True,
            )
            mock_get.return_value = mock_connection
            mock_delete.return_value = True

            result = await service.delete_connection(session=session, connection_id=connection_id, user_id=user_id)

            assert result is True
            mock_delete.assert_called_once_with(session, connection_id, user_id)

    @pytest.mark.asyncio
    async def test_update_connection(self):
        """Test updating a connection."""
        service = ConnectorService()
        session = MagicMock()
        connection_id = uuid4()
        user_id = uuid4()
        update_data = {"name": "Updated Name"}

        expected_connection = ConnectorConnection(
            id=connection_id,
            user_id=user_id,
            connector_type="google_drive",
            name="Updated Name",
            config={},
            is_active=True,
        )

        with (
            patch("langflow.services.connectors.service.db_get_connection", new_callable=AsyncMock) as mock_get,
            patch("langflow.services.connectors.service.db_update_connection", new_callable=AsyncMock) as mock_update,
        ):
            # Mock the connection for validation
            mock_connection = ConnectorConnection(
                id=connection_id,
                user_id=user_id,
                connector_type="google_drive",
                name="Old Name",
                config={},
                is_active=True,
            )
            mock_get.return_value = mock_connection
            mock_update.return_value = expected_connection

            result = await service.update_connection(
                session=session, connection_id=connection_id, user_id=user_id, update_data=update_data
            )

            assert result == expected_connection
            assert result.name == "Updated Name"
            mock_update.assert_called_once_with(session, connection_id, user_id, update_data)

    @pytest.mark.asyncio
    async def test_get_oauth_url_not_implemented(self):
        """Test that get_oauth_url raises NotImplementedError."""
        service = ConnectorService()
        connection_id = uuid4()
        user_id = uuid4()

        with pytest.raises(NotImplementedError, match="OAuth URL generation not yet implemented"):
            await service.get_oauth_url(
                connection_id=connection_id, user_id=user_id, redirect_uri="http://localhost/callback"
            )

    @pytest.mark.asyncio
    async def test_complete_oauth_not_implemented(self):
        """Test that complete_oauth raises NotImplementedError."""
        service = ConnectorService()
        session = MagicMock()
        connection_id = uuid4()
        user_id = uuid4()

        with pytest.raises(NotImplementedError, match="OAuth completion not yet implemented"):
            await service.complete_oauth(
                session=session, connection_id=connection_id, user_id=user_id, code="auth_code_123"
            )

    @pytest.mark.asyncio
    async def test_sync_files_returns_task_id(self):
        """Test that sync_files returns a task ID."""
        service = ConnectorService()
        session = MagicMock()
        connection_id = uuid4()
        user_id = uuid4()

        # Mock the connection for validation
        mock_connection = ConnectorConnection(
            id=connection_id,
            user_id=user_id,
            connector_type="google_drive",
            name="Test",
            config={},
            is_active=True,
        )

        with patch("langflow.services.connectors.service.db_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_connection

            result = await service.sync_files(session=session, connection_id=connection_id, user_id=user_id)

            # Should return a task ID (UUID string)
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_connector_instance_not_implemented(self):
        """Test that get_connector_instance raises NotImplementedError."""
        service = ConnectorService()
        connection = ConnectorConnection(
            id=uuid4(), user_id=uuid4(), connector_type="google_drive", name="Test", config={}, is_active=True
        )

        with pytest.raises(NotImplementedError, match="Connector instantiation not yet implemented"):
            await service.get_connector_instance(connection=connection)
