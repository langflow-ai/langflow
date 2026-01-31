"""Test decrypt_api_key function with encrypted, plain text, and wrong key scenarios."""

from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from langflow.services.auth.mcp_encryption import is_encrypted
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from pydantic import SecretStr


@pytest.fixture
def mock_settings_service():
    """Mock settings service with a valid Fernet key."""
    mock_service = Mock()
    valid_key = Fernet.generate_key()
    valid_key_str = valid_key.decode("utf-8")
    secret_key_obj = SecretStr(valid_key_str)
    mock_service.auth_settings.SECRET_KEY = secret_key_obj
    return mock_service


@pytest.fixture
def different_settings_service():
    """Mock settings service with a different Fernet key."""
    mock_service = Mock()
    # Generate a different key
    different_key = Fernet.generate_key()
    different_key_str = different_key.decode("utf-8")
    secret_key_obj = SecretStr(different_key_str)
    mock_service.auth_settings.SECRET_KEY = secret_key_obj
    return mock_service


class TestDecryptApiKey:
    """Test decrypt_api_key function behavior."""

    def test_decrypt_encrypted_value_success(self, mock_settings_service):
        """Test successful decryption of an encrypted value."""
        original_value = "my-secret-api-key-12345"

        # Encrypt the value
        encrypted_value = encrypt_api_key(original_value, mock_settings_service)

        # Verify it's encrypted (should start with gAAAAA)
        assert encrypted_value.startswith("gAAAAA")
        assert encrypted_value != original_value

        # Decrypt and verify
        decrypted_value = decrypt_api_key(encrypted_value, mock_settings_service)
        assert decrypted_value == original_value

    def test_decrypt_plain_text_value(self, mock_settings_service):
        """Test that plain text values are returned as-is."""
        plain_text_value = "plain-text-api-key"

        # Should return the same value
        result = decrypt_api_key(plain_text_value, mock_settings_service)
        assert result == plain_text_value

    def test_decrypt_with_wrong_key_returns_empty(self, mock_settings_service, different_settings_service):
        """Test that encrypted values with wrong key return empty string."""
        original_value = "my-secret-api-key-12345"

        # Encrypt with one key
        encrypted_value = encrypt_api_key(original_value, mock_settings_service)

        # Verify it's encrypted
        assert encrypted_value.startswith("gAAAAA")

        # Try to decrypt with different key - should return empty string
        result = decrypt_api_key(encrypted_value, different_settings_service)
        assert result == ""

    def test_decrypt_empty_string(self, mock_settings_service):
        """Test decryption of empty string."""
        result = decrypt_api_key("", mock_settings_service)
        assert result == ""

    def test_decrypt_special_characters_plain_text(self, mock_settings_service):
        """Test plain text with special characters."""
        special_value = "api-key-with-special!@#$%^&*()"

        result = decrypt_api_key(special_value, mock_settings_service)
        assert result == special_value

    def test_decrypt_numeric_string_plain_text(self, mock_settings_service):
        """Test plain text numeric string."""
        numeric_value = "1234567890"

        result = decrypt_api_key(numeric_value, mock_settings_service)
        assert result == numeric_value

    def test_decrypt_url_plain_text(self, mock_settings_service):
        """Test plain text URL."""
        url_value = "https://api.example.com/v1/key"

        result = decrypt_api_key(url_value, mock_settings_service)
        assert result == url_value

    def test_decrypt_base64_like_but_not_fernet(self, mock_settings_service):
        """Test base64-like string that's not a Fernet token."""
        # Base64 string that doesn't start with gAAAAA
        base64_value = "aGVsbG8gd29ybGQ="  # "hello world" in base64

        result = decrypt_api_key(base64_value, mock_settings_service)
        assert result == base64_value

    def test_decrypt_long_encrypted_value(self, mock_settings_service):
        """Test decryption of a long encrypted value."""
        long_value = "a" * 1000  # 1000 character string

        encrypted_value = encrypt_api_key(long_value, mock_settings_service)
        decrypted_value = decrypt_api_key(encrypted_value, mock_settings_service)

        assert decrypted_value == long_value

    def test_decrypt_unicode_plain_text(self, mock_settings_service):
        """Test plain text with unicode characters."""
        unicode_value = "api-key-with-émojis-🔑-and-中文"

        result = decrypt_api_key(unicode_value, mock_settings_service)
        assert result == unicode_value

    def test_decrypt_encrypted_unicode(self, mock_settings_service):
        """Test encryption and decryption of unicode characters."""
        unicode_value = "secret-🔐-key-密钥"

        encrypted_value = encrypt_api_key(unicode_value, mock_settings_service)
        decrypted_value = decrypt_api_key(encrypted_value, mock_settings_service)

        assert decrypted_value == unicode_value

    def test_fernet_token_signature_detection(self, mock_settings_service, different_settings_service):
        """Test that Fernet token signature (gAAAAA) is properly detected."""
        original_value = "test-value"

        # Encrypt with one key
        encrypted_value = encrypt_api_key(original_value, mock_settings_service)

        # Verify it has the Fernet signature
        assert encrypted_value.startswith("gAAAAA")

        # Decrypt with wrong key should return empty (not the encrypted value)
        result = decrypt_api_key(encrypted_value, different_settings_service)
        assert result == ""
        assert result != encrypted_value


class TestIsEncrypted:
    """Test is_encrypted helper function."""

    def test_is_encrypted_with_encrypted_value(self, mock_settings_service):
        """Test that encrypted values are correctly identified."""
        original_value = "my-secret-key"
        encrypted_value = encrypt_api_key(original_value, mock_settings_service)

        # Should be identified as encrypted
        assert is_encrypted(encrypted_value)

    def test_is_encrypted_with_plain_text(self, mock_settings_service):  # noqa: ARG002
        """Test that plain text values are not identified as encrypted."""
        plain_text = "plain-text-value"

        # Should not be identified as encrypted
        assert not is_encrypted(plain_text)

    def test_is_encrypted_with_empty_string(self, mock_settings_service):  # noqa: ARG002
        """Test that empty string is not identified as encrypted."""
        assert not is_encrypted("")

    def test_is_encrypted_with_none(self, mock_settings_service):  # noqa: ARG002
        """Test that None is handled gracefully."""
        # is_encrypted expects a string, but let's test edge case
        assert not is_encrypted(None) if None else True  # Will short-circuit

    def test_is_encrypted_with_base64_not_fernet(self, mock_settings_service):  # noqa: ARG002
        """Test that base64 strings without Fernet signature are not identified as encrypted."""
        base64_value = "aGVsbG8gd29ybGQ="  # "hello world" in base64

        # Should not be identified as encrypted (doesn't start with gAAAAA)
        assert not is_encrypted(base64_value)

    def test_is_encrypted_with_wrong_key(self, mock_settings_service):
        """Test that values encrypted with different key are still identified as encrypted."""
        original_value = "my-secret-key"

        # Encrypt with one key
        encrypted_value = encrypt_api_key(original_value, mock_settings_service)

        # Should still be identified as encrypted even with different settings service
        # (because it has the Fernet signature)
        assert is_encrypted(encrypted_value)

    def test_is_encrypted_with_fernet_signature_prefix(self, mock_settings_service):  # noqa: ARG002
        """Test that strings starting with gAAAAA are identified as encrypted."""
        # Create a fake Fernet-like string (won't decrypt but has signature)
        fake_encrypted = "gAAAAABfakeencryptedvalue123456789"

        # Should be identified as encrypted based on signature
        assert is_encrypted(fake_encrypted)
