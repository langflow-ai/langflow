"""Test MCP authentication encryption functionality."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from langflow.services.auth.mcp_encryption import (
    decrypt_auth_settings,
    encrypt_auth_settings,
    is_encrypted,
)
from langflow.services.auth.service import AuthService
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr


@pytest.fixture
def mock_auth_service(tmp_path):
    """Create a real AuthService for testing encryption."""
    # Create real auth settings with a valid Fernet key
    valid_key = Fernet.generate_key()
    valid_key_str = valid_key.decode("utf-8")

    auth_settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    auth_settings.SECRET_KEY = SecretStr(valid_key_str)

    settings_service = SimpleNamespace(
        auth_settings=auth_settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    return AuthService(settings_service)


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
        "oauth_client_secret": "super-secret-password-123",  # pragma: allowlist secret
        "oauth_auth_url": "https://oauth.example.com/auth",
        "oauth_token_url": "https://oauth.example.com/token",
        "oauth_mcp_scope": "read write",
        "oauth_provider_scope": "user:email",
    }


class TestMCPEncryption:
    """Test MCP encryption functionality."""

    @patch("langflow.services.auth.utils.get_auth_service")
    def test_encrypt_auth_settings(self, mock_get_auth, mock_auth_service, sample_auth_settings):
        """Test that sensitive fields are encrypted."""
        mock_get_auth.return_value = mock_auth_service

        # Encrypt the settings
        encrypted = encrypt_auth_settings(sample_auth_settings)

        # Check that sensitive fields are encrypted
        assert encrypted is not None
        assert encrypted["oauth_client_secret"] != sample_auth_settings["oauth_client_secret"]

        # Check that non-sensitive fields remain unchanged
        assert encrypted["auth_type"] == sample_auth_settings["auth_type"]
        assert encrypted["oauth_host"] == sample_auth_settings["oauth_host"]
        assert encrypted["oauth_client_id"] == sample_auth_settings["oauth_client_id"]

    @patch("langflow.services.auth.utils.get_auth_service")
    def test_decrypt_auth_settings(self, mock_get_auth, mock_auth_service, sample_auth_settings):
        """Test that encrypted fields can be decrypted."""
        mock_get_auth.return_value = mock_auth_service

        # First encrypt the settings
        encrypted = encrypt_auth_settings(sample_auth_settings)

        # Then decrypt them
        decrypted = decrypt_auth_settings(encrypted)

        # Verify all fields match the original
        assert decrypted == sample_auth_settings

    def test_encrypt_none_returns_none(self):
        """Test that encrypting None returns None."""
        result = encrypt_auth_settings(None)
        assert result is None

    def test_decrypt_none_returns_none(self):
        """Test that decrypting None returns None."""
        result = decrypt_auth_settings(None)
        assert result is None

    def test_encrypt_empty_dict(self):
        """Test that encrypting empty dict returns empty dict."""
        result = encrypt_auth_settings({})
        assert result == {}

    @patch("langflow.services.auth.utils.get_auth_service")
    def test_idempotent_encryption(self, mock_get_auth, mock_auth_service, sample_auth_settings):
        """Test that encrypting already encrypted data doesn't double-encrypt."""
        mock_get_auth.return_value = mock_auth_service

        # First encryption
        encrypted_once = encrypt_auth_settings(sample_auth_settings)

        # Second encryption should detect already encrypted fields
        encrypted_twice = encrypt_auth_settings(encrypted_once)

        # Should be the same
        assert encrypted_once == encrypted_twice

    @patch("langflow.services.auth.utils.get_auth_service")
    def test_partial_auth_settings(self, mock_get_auth, mock_auth_service):
        """Test encryption with only some sensitive fields present."""
        mock_get_auth.return_value = mock_auth_service

        partial_settings = {
            "auth_type": "api",
            "api_key": "sk-test-api-key-123",  # pragma: allowlist secret
            "username": "admin",
        }

        encrypted = encrypt_auth_settings(partial_settings)

        # API key should be encrypted
        assert encrypted["api_key"] != partial_settings["api_key"]

        # Other fields unchanged
        assert encrypted["auth_type"] == partial_settings["auth_type"]
        assert encrypted["username"] == partial_settings["username"]

    @patch("langflow.services.auth.utils.get_auth_service")
    def test_backward_compatibility(self, mock_get_auth, mock_auth_service):
        """Test that plaintext data is handled gracefully during decryption."""
        mock_get_auth.return_value = mock_auth_service

        # Simulate legacy plaintext data
        plaintext_settings = {
            "auth_type": "oauth",
            "oauth_client_secret": "plaintext-secret",  # pragma: allowlist secret
            "oauth_client_id": "client-123",
        }

        # Decryption should handle plaintext gracefully
        decrypted = decrypt_auth_settings(plaintext_settings)

        # Should return the same data
        assert decrypted == plaintext_settings

    @patch("langflow.services.auth.utils.get_auth_service")
    def test_is_encrypted(self, mock_get_auth, mock_auth_service):
        """Test the is_encrypted helper function."""
        mock_get_auth.return_value = mock_auth_service

        # Test with plaintext
        assert not is_encrypted("plaintext-value")
        assert not is_encrypted("")
        assert not is_encrypted(None)

        # Test with encrypted value
        encrypted_value = mock_auth_service.encrypt_api_key("secret-value")
        assert is_encrypted(encrypted_value)
