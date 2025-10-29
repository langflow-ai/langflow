"""Test connector service security enhancements."""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.connectors.encryption import get_encryption
from langflow.services.connectors.service import ConnectorPermissionError, ConnectorService, RateLimitError
from langflow.services.database.models.connector import ConnectorConnection


@pytest.fixture
def connector_service():
    """Create a connector service instance."""
    return ConnectorService()


@pytest.fixture
def sample_connection():
    """Create a sample connection."""
    return ConnectorConnection(
        id=uuid4(),
        user_id=uuid4(),
        connector_type="google_drive",
        name="Test Drive",
        config={"client_id": "test_id"},
        knowledge_base_id=None,
        is_active=True,
    )


@pytest.fixture
def encryption():
    """Get encryption instance."""
    return get_encryption()


class TestTokenEncryption:
    """Test token encryption functionality."""

    def test_encrypt_decrypt_token(self, encryption):
        """Test that tokens can be encrypted and decrypted."""
        original_token = "super_secret_token_12345"  # noqa: S105

        # Encrypt the token
        encrypted = encryption.encrypt_token(original_token)

        # Verify it's different from original
        assert encrypted != original_token
        assert len(encrypted) > 0

        # Decrypt and verify
        decrypted = encryption.decrypt_token(encrypted)
        assert decrypted == original_token

    def test_encrypt_decrypt_config(self, encryption):
        """Test that config dictionaries can be encrypted and decrypted."""
        original_config = {
            "client_id": "test_client",
            "client_secret": "secret_value",  # pragma: allowlist secret
            "api_key": "api_key_123",  # pragma: allowlist secret
        }

        # Encrypt the config
        encrypted = encryption.encrypt_config(original_config)

        # Verify it's encrypted
        assert encrypted != str(original_config)
        assert isinstance(encrypted, str)

        # Decrypt and verify
        decrypted = encryption.decrypt_config(encrypted)
        assert decrypted == original_config

    def test_empty_token_handling(self, encryption):
        """Test that empty tokens are handled correctly."""
        assert encryption.encrypt_token("") == ""
        assert encryption.decrypt_token("") == ""


class TestConnectorService:
    """Test connector service security features."""

    @pytest.mark.asyncio
    async def test_ownership_validation_success(self, connector_service, sample_connection):
        """Test successful ownership validation."""
        user_id = sample_connection.user_id
        connection_id = sample_connection.id
        mock_session = MagicMock()

        # Mock the database get_connection to return our sample
        with patch("langflow.services.connectors.service.db_get_connection") as mock_get:
            mock_get.return_value = sample_connection

            # This should succeed
            result = await connector_service._validate_user_ownership(mock_session, connection_id, user_id, "test")
            assert result == sample_connection

    @pytest.mark.asyncio
    async def test_ownership_validation_wrong_user(self, connector_service, sample_connection):
        """Test ownership validation fails for wrong user."""
        wrong_user_id = uuid4()
        connection_id = sample_connection.id
        mock_session = MagicMock()

        # Mock the database get_connection to return our sample
        with patch("langflow.services.connectors.service.db_get_connection") as mock_get:
            mock_get.return_value = sample_connection

            # This should fail with PermissionError
            with pytest.raises(ConnectorPermissionError, match="Access denied"):
                await connector_service._validate_user_ownership(mock_session, connection_id, wrong_user_id, "test")

    @pytest.mark.asyncio
    async def test_ownership_validation_not_found(self, connector_service):
        """Test ownership validation fails when connection not found."""
        user_id = uuid4()
        connection_id = uuid4()
        mock_session = MagicMock()

        # Mock the database get_connection to return None
        with patch("langflow.services.connectors.service.db_get_connection") as mock_get:
            mock_get.return_value = None

            # This should fail with PermissionError
            with pytest.raises(ConnectorPermissionError, match="Connection not found"):
                await connector_service._validate_user_ownership(mock_session, connection_id, user_id, "test")

    @pytest.mark.asyncio
    async def test_create_connection_encrypts_secrets(self, connector_service):
        """Test that create_connection encrypts sensitive fields."""
        user_id = uuid4()
        mock_session = MagicMock()

        # Config with sensitive data
        config = {
            "client_id": "public_id",
            "client_secret": "secret_value",  # pragma: allowlist secret
            "api_key": "api_key_123",  # pragma: allowlist secret
        }

        with patch("langflow.services.connectors.service.db_create_connection") as mock_create:
            mock_create.return_value = MagicMock(id=uuid4())

            await connector_service.create_connection(
                mock_session,
                user_id,
                "google_drive",
                "Test Drive",
                config,
            )

            # Check that the config passed to db_create_connection has encrypted values
            call_args = mock_create.call_args[0][1]
            saved_config = call_args["config"]

            # client_secret and api_key should be encrypted
            assert saved_config["client_secret"] != "secret_value"  # noqa: S105  # pragma: allowlist secret
            assert saved_config["api_key"] != "api_key_123"  # pragma: allowlist secret
            # client_id should remain unchanged
            assert saved_config["client_id"] == "public_id"

    @pytest.mark.asyncio
    async def test_get_connection_decrypts_secrets(self, connector_service, sample_connection):
        """Test that get_connection decrypts sensitive fields."""
        user_id = sample_connection.user_id
        connection_id = sample_connection.id
        mock_session = MagicMock()

        # Add encrypted secrets to config
        encryption = get_encryption()
        sample_connection.config = {
            "client_id": "public_id",
            "client_secret": encryption.encrypt_token("secret_value"),  # pragma: allowlist secret
            "api_key": encryption.encrypt_token("api_key_123"),  # pragma: allowlist secret
        }

        with patch("langflow.services.connectors.service.db_get_connection") as mock_get:
            mock_get.return_value = sample_connection

            result = await connector_service.get_connection(mock_session, connection_id, user_id)

            # Check that secrets are decrypted
            assert result.config["client_secret"] == "secret_value"  # noqa: S105  # pragma: allowlist secret
            assert result.config["api_key"] == "api_key_123"  # pragma: allowlist secret
            assert result.config["client_id"] == "public_id"

    @pytest.mark.asyncio
    async def test_connection_level_locking(self, connector_service):
        """Test that connection-level locks prevent race conditions."""
        user_id = uuid4()
        connection_id = uuid4()
        mock_session = MagicMock()

        # Track how many times validate_user_ownership is called
        call_count = 0

        async def mock_validate(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate some work
            return MagicMock()

        connector_service._validate_user_ownership = mock_validate

        with patch("langflow.services.connectors.service.db_update_connection") as mock_update:
            mock_update.return_value = MagicMock()

            # Try to update the same connection concurrently
            tasks = [
                connector_service.update_connection(mock_session, connection_id, user_id, {"name": f"Update {i}"})
                for i in range(3)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete without errors
            assert all(not isinstance(r, Exception) for r in results)
            # Operations should be serialized due to lock
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limiting(self, connector_service):
        """Test that rate limiting prevents too many concurrent operations."""
        user_id = uuid4()
        connector_service.max_concurrent_operations = 2

        # Get the semaphore for this user
        semaphore = connector_service._get_user_semaphore(user_id)

        # Acquire all available slots
        await semaphore.acquire()
        await semaphore.acquire()

        # Now the semaphore should be locked
        assert semaphore.locked()

        # sync_files should raise RateLimitError
        mock_session = MagicMock()
        with pytest.raises(RateLimitError, match="Too many concurrent operations"):
            await connector_service.sync_files(mock_session, uuid4(), user_id)

        # Release one slot
        semaphore.release()

        # Now it should not be locked
        assert not semaphore.locked()

    @pytest.mark.asyncio
    async def test_store_oauth_token_encryption(self, connector_service, sample_connection):
        """Test that OAuth tokens are encrypted when stored."""
        user_id = sample_connection.user_id
        connection_id = sample_connection.id
        mock_session = MagicMock()

        access_token = "access_token_12345"  # noqa: S105
        refresh_token = "refresh_token_67890"  # noqa: S105

        with (
            patch("langflow.services.connectors.service.db_get_connection") as mock_get,
            patch("langflow.services.database.models.connector.get_oauth_token") as mock_get_token,
            patch("langflow.services.connectors.service.create_oauth_token") as mock_create,
        ):
            mock_get.return_value = sample_connection
            mock_get_token.return_value = None  # No existing token
            mock_create.return_value = MagicMock()

            await connector_service.store_oauth_token(
                mock_session,
                connection_id,
                user_id,
                access_token,
                refresh_token,
                expires_in=3600,
            )

            # Check that tokens were encrypted
            assert mock_create.called
            call_args = mock_create.call_args[0][1]
            assert call_args["encrypted_access_token"] != access_token
            assert call_args["encrypted_refresh_token"] != refresh_token

            # Verify they can be decrypted correctly
            encryption = get_encryption()
            decrypted_access = encryption.decrypt_token(call_args["encrypted_access_token"])
            decrypted_refresh = encryption.decrypt_token(call_args["encrypted_refresh_token"])
            assert decrypted_access == access_token
            assert decrypted_refresh == refresh_token

    @pytest.mark.asyncio
    async def test_webhook_renewal_scheduling(self, connector_service):
        """Test that webhook renewal is scheduled for supported connectors."""
        connection_id = uuid4()

        # Schedule renewal
        await connector_service._schedule_webhook_renewal(connection_id)

        # Check that task was created
        assert connection_id in connector_service._subscription_renewal_tasks
        task = connector_service._subscription_renewal_tasks[connection_id]
        assert not task.done()

        # Cancel the task
        task.cancel()
        await asyncio.sleep(0.01)  # Give it time to cancel

        # Task should be cancelled
        assert task.cancelled()
