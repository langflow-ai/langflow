"""Test MCP authentication encryption functionality."""

from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet
from langflow.services.auth.mcp_encryption import (
    decrypt_auth_settings,
    encrypt_auth_settings,
    is_encrypted,
)
from pydantic import SecretStr


@pytest.fixture
def mock_settings_service():
    """Mock settings service for testing."""
    mock_service = Mock()
    # Generate a valid Fernet key that's already properly formatted
    # Fernet.generate_key() returns a URL-safe base64-encoded 32-byte key
    valid_key = Fernet.generate_key()
    # Decode it to string for storage
    valid_key_str = valid_key.decode("utf-8")

    # Create a proper SecretStr object
    secret_key_obj = SecretStr(valid_key_str)
    mock_service.auth_settings.SECRET_KEY = secret_key_obj
    return mock_service


@pytest.fixture
def sample_auth_settings():
    """Sample auth settings with sensitive data."""
    return {
        "auth_type": "oauth",
        "oauth_host": "localhost",
        "oauth_port": "3000",
        "oauth_server_url": "http://localhost:3000",
        "oauth_callback_path": "/callback",
        "oauth_client_id": "my-client-id",
        "oauth_client_secret": "super-secret-password-123",
        "oauth_auth_url": "https://oauth.example.com/auth",
        "oauth_token_url": "https://oauth.example.com/token",
        "oauth_mcp_scope": "read write",
        "oauth_provider_scope": "user:email",
    }


class TestMCPEncryption:
    """Test MCP encryption functionality."""

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_encrypt_auth_settings(self, mock_get_settings, mock_settings_service, sample_auth_settings):
        """Test that sensitive fields are encrypted."""
        mock_get_settings.return_value = mock_settings_service

        # Encrypt the settings
        encrypted = encrypt_auth_settings(sample_auth_settings)

        # Check that sensitive fields are encrypted
        assert encrypted is not None
        assert encrypted["oauth_client_secret"] != sample_auth_settings["oauth_client_secret"]

        # Check that non-sensitive fields remain unchanged
        assert encrypted["auth_type"] == sample_auth_settings["auth_type"]
        assert encrypted["oauth_host"] == sample_auth_settings["oauth_host"]
        assert encrypted["oauth_client_id"] == sample_auth_settings["oauth_client_id"]

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_decrypt_auth_settings(self, mock_get_settings, mock_settings_service, sample_auth_settings):
        """Test that encrypted fields can be decrypted."""
        mock_get_settings.return_value = mock_settings_service

        # First encrypt the settings
        encrypted = encrypt_auth_settings(sample_auth_settings)

        # Then decrypt them
        decrypted = decrypt_auth_settings(encrypted)

        # Verify all fields match the original
        assert decrypted == sample_auth_settings

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_encrypt_none_returns_none(self, mock_get_settings):  # noqa: ARG002
        """Test that encrypting None returns None."""
        result = encrypt_auth_settings(None)
        assert result is None

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_decrypt_none_returns_none(self, mock_get_settings):  # noqa: ARG002
        """Test that decrypting None returns None."""
        result = decrypt_auth_settings(None)
        assert result is None

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_encrypt_empty_dict(self, mock_get_settings):  # noqa: ARG002
        """Test that encrypting empty dict returns empty dict."""
        result = encrypt_auth_settings({})
        assert result == {}

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_idempotent_encryption(self, mock_get_settings, mock_settings_service, sample_auth_settings):
        """Test that encrypting already encrypted data doesn't double-encrypt."""
        mock_get_settings.return_value = mock_settings_service

        # First encryption
        encrypted_once = encrypt_auth_settings(sample_auth_settings)

        # Second encryption should detect already encrypted fields
        encrypted_twice = encrypt_auth_settings(encrypted_once)

        # Should be the same
        assert encrypted_once == encrypted_twice

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_partial_auth_settings(self, mock_get_settings, mock_settings_service):
        """Test encryption with only some sensitive fields present."""
        mock_get_settings.return_value = mock_settings_service

        partial_settings = {
            "auth_type": "api",
            "api_key": "sk-test-api-key-123",
            "username": "admin",
        }

        encrypted = encrypt_auth_settings(partial_settings)

        # API key should be encrypted
        assert encrypted["api_key"] != partial_settings["api_key"]

        # Other fields unchanged
        assert encrypted["auth_type"] == partial_settings["auth_type"]
        assert encrypted["username"] == partial_settings["username"]

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_backward_compatibility(self, mock_get_settings, mock_settings_service):
        """Test that plaintext data is handled gracefully during decryption."""
        mock_get_settings.return_value = mock_settings_service

        # Simulate legacy plaintext data
        plaintext_settings = {
            "auth_type": "oauth",
            "oauth_client_secret": "plaintext-secret",
            "oauth_client_id": "client-123",
        }

        # Decryption should handle plaintext gracefully
        decrypted = decrypt_auth_settings(plaintext_settings)

        # Should return the same data
        assert decrypted == plaintext_settings

    @patch("langflow.services.auth.mcp_encryption.get_settings_service")
    def test_is_encrypted(self, mock_get_settings, mock_settings_service):
        """Test the is_encrypted helper function."""
        mock_get_settings.return_value = mock_settings_service

        # Test with plaintext
        assert not is_encrypted("plaintext-value")
        assert not is_encrypted("")
        assert not is_encrypted(None)

        # Test with encrypted value
        from langflow.services.auth import utils as auth_utils

        encrypted_value = auth_utils.encrypt_api_key("secret-value", mock_settings_service)
        assert is_encrypted(encrypted_value)
