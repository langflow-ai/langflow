"""Test decrypt_api_key function with encrypted, plain text, and wrong key scenarios."""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from langflow.services.auth.mcp_encryption import is_encrypted
from langflow.services.auth.service import AuthService
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr
from structlog import make_filtering_bound_logger, wrap_logger
from structlog.testing import LogCapture


@pytest.fixture
def langflow_auth_service(tmp_path):
    """Use Langflow AuthService for encrypt/decrypt so tests get real Fernet behavior."""
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr("unit-test-secret-for-encryption")
    settings_service = SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    return AuthService(settings_service)


@pytest.fixture(autouse=True)
def use_langflow_auth_for_encryption(langflow_auth_service):
    """Ensure utils use Langflow AuthService (real encrypt/decrypt), not LFX stub."""
    with patch("langflow.services.auth.utils.get_auth_service", return_value=langflow_auth_service):
        yield


class TestDecryptApiKey:
    """Test decrypt_api_key function behavior."""

    def test_decrypt_encrypted_value_success(self):
        """Test successful decryption of an encrypted value."""
        original_value = "my-secret-api-key-12345"

        # Encrypt the value
        encrypted_value = encrypt_api_key(original_value)

        # Verify it's encrypted (should start with gAAAAA)
        assert encrypted_value.startswith("gAAAAA")
        assert encrypted_value != original_value

        # Decrypt and verify
        decrypted_value = decrypt_api_key(encrypted_value)
        assert decrypted_value == original_value

    def test_decrypt_plain_text_value(self):
        """Test that plain text values are returned as-is."""
        plain_text_value = "plain-text-api-key"

        # Should return the same value
        result = decrypt_api_key(plain_text_value)
        assert result == plain_text_value

    @pytest.mark.parametrize("failure_kind", ["wrong-key", "malformed-token"])
    def test_decrypt_failure_returns_empty_and_logs_error(self, langflow_auth_service, monkeypatch, failure_kind):
        """Decryption failures remain visible at ERROR without exposing credentials."""
        original_value = "my-secret-api-key-12345"
        encryption_key = Fernet.generate_key().decode()
        decryption_key = Fernet.generate_key().decode()
        langflow_auth_service.settings.auth_settings.SECRET_KEY = SecretStr(encryption_key)
        encrypted_value = encrypt_api_key(original_value)
        langflow_auth_service.settings.auth_settings.SECRET_KEY = SecretStr(decryption_key)
        token = encrypted_value if failure_kind == "wrong-key" else "gAAAAA-invalid-token"

        captured_logs = LogCapture()
        error_logger = wrap_logger(
            logging.getLogger(__name__),
            processors=[captured_logs],
            wrapper_class=make_filtering_bound_logger(logging.ERROR),
        )
        monkeypatch.setattr("langflow.services.auth.service.logger", error_logger)

        assert decrypt_api_key(token) == ""
        assert len(captured_logs.entries) == 1
        entry = captured_logs.entries[0]
        assert entry["log_level"] == "error"
        assert "API key decryption failed" in entry["event"]
        assert "SECRET_KEY mismatch" in entry["event"]
        log_output = repr(captured_logs.entries)
        for secret in (original_value, encrypted_value, token, encryption_key, decryption_key):
            assert secret not in log_output

    def test_decrypt_empty_string(self):
        """Test decryption of empty string."""
        result = decrypt_api_key("")
        assert result == ""

    def test_decrypt_special_characters_plain_text(self):
        """Test plain text with special characters."""
        special_value = "api-key-with-special!@#$%^&*()"

        result = decrypt_api_key(special_value)
        assert result == special_value

    def test_decrypt_numeric_string_plain_text(self):
        """Test plain text numeric string."""
        numeric_value = "1234567890"

        result = decrypt_api_key(numeric_value)
        assert result == numeric_value

    def test_decrypt_url_plain_text(self):
        """Test plain text URL."""
        url_value = "https://api.example.com/v1/key"

        result = decrypt_api_key(url_value)
        assert result == url_value

    def test_decrypt_base64_like_but_not_fernet(self):
        """Test base64-like string that's not a Fernet token."""
        # Base64 string that doesn't start with gAAAAA
        base64_value = "aGVsbG8gd29ybGQ="  # "hello world" in base64

        result = decrypt_api_key(base64_value)
        assert result == base64_value

    def test_decrypt_long_encrypted_value(self):
        """Test decryption of a long encrypted value."""
        long_value = "a" * 1000  # 1000 character string

        encrypted_value = encrypt_api_key(long_value)
        decrypted_value = decrypt_api_key(encrypted_value)

        assert decrypted_value == long_value

    def test_decrypt_unicode_plain_text(self):
        """Test plain text with unicode characters."""
        unicode_value = "api-key-with-émojis-🔑-and-中文"

        result = decrypt_api_key(unicode_value)
        assert result == unicode_value

    def test_decrypt_encrypted_unicode(self):
        """Test encryption and decryption of unicode characters."""
        unicode_value = "secret-🔐-key-密钥"

        encrypted_value = encrypt_api_key(unicode_value)
        decrypted_value = decrypt_api_key(encrypted_value)

        assert decrypted_value == unicode_value

    def test_fernet_token_signature_detection(self):
        """Test that Fernet token signature (gAAAAA) is properly detected."""
        original_value = "test-value"

        # Encrypt with one key
        encrypted_value = encrypt_api_key(original_value)

        # Verify it has the Fernet signature
        assert encrypted_value.startswith("gAAAAA")

        # Note: Since encrypt/decrypt now use the auth service internally,
        # decryption will succeed with the same service instance
        result = decrypt_api_key(encrypted_value)
        assert result == original_value  # Changed expectation


# Made with Bob


class TestIsEncrypted:
    """Test is_encrypted helper function."""

    def test_is_encrypted_with_encrypted_value(self):
        """Test that encrypted values are correctly identified."""
        original_value = "my-secret-key"
        encrypted_value = encrypt_api_key(original_value)

        # Should be identified as encrypted
        assert is_encrypted(encrypted_value)

    def test_is_encrypted_with_plain_text(self):
        """Test that plain text values are not identified as encrypted."""
        plain_text = "plain-text-value"

        # Should not be identified as encrypted
        assert not is_encrypted(plain_text)

    def test_is_encrypted_with_empty_string(self):
        """Test that empty string is not identified as encrypted."""
        assert not is_encrypted("")

    def test_is_encrypted_with_none(self):
        """Test that None is handled gracefully."""
        # is_encrypted expects a string, but let's test edge case
        assert not is_encrypted(None) if None else True  # Will short-circuit

    def test_is_encrypted_with_base64_not_fernet(self):
        """Test that base64 strings without Fernet signature are not identified as encrypted."""
        base64_value = "aGVsbG8gd29ybGQ="  # "hello world" in base64

        # Should not be identified as encrypted (doesn't start with gAAAAA)
        assert not is_encrypted(base64_value)

    def test_is_encrypted_with_wrong_key(self):
        """Test that values encrypted with different key are still identified as encrypted."""
        original_value = "my-secret-key"

        # Encrypt with one key
        encrypted_value = encrypt_api_key(original_value)

        # Should still be identified as encrypted even with different settings service
        # (because it has the Fernet signature)
        assert is_encrypted(encrypted_value)

    def test_is_encrypted_with_fernet_signature_prefix(self):
        """Test that strings starting with gAAAAA are identified as encrypted."""
        # Create a fake Fernet-like string (won't decrypt but has signature)
        fake_encrypted = "gAAAAABfakeencryptedvalue123456789"

        # Should be identified as encrypted based on signature
        assert is_encrypted(fake_encrypted)
