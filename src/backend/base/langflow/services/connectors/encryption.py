"""Encryption utilities for connector tokens and sensitive data."""

import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet
from lfx.log.logger import logger


class TokenEncryption:
    """Handles encryption and decryption of OAuth tokens and sensitive connector data."""

    def __init__(self, master_key: str | None = None):
        """Initialize encryption with master key.

        Args:
            master_key: Master encryption key. If not provided, uses environment variable
                       or generates a new one (not recommended for production).
        """
        self.cipher_suite = self._initialize_cipher(master_key)

    def _initialize_cipher(self, master_key: str | None = None) -> Fernet:
        """Initialize Fernet cipher.

        Args:
            master_key: Master key for encryption

        Returns:
            Configured Fernet cipher
        """
        if master_key:
            # Use provided key (should be base64 encoded)
            key = master_key.encode() if isinstance(master_key, str) else master_key
            # Ensure it's valid base64
            try:
                base64.urlsafe_b64decode(key)
            except (ValueError, TypeError):
                # If not valid base64, generate key from string
                import hashlib

                hash_key = hashlib.sha256(master_key.encode()).digest()
                key = base64.urlsafe_b64encode(hash_key)
        else:
            # Try to get from environment
            env_key = os.getenv("LANGFLOW_CONNECTOR_ENCRYPTION_KEY")
            if env_key:
                key = env_key.encode()
                # Validate it's proper format
                try:
                    base64.urlsafe_b64decode(key)
                except (ValueError, TypeError):
                    # Generate from env string
                    import hashlib

                    hash_key = hashlib.sha256(env_key.encode()).digest()
                    key = base64.urlsafe_b64encode(hash_key)
            else:
                # Generate new key (should only happen in development)
                logger.warning(
                    "No encryption key provided. Generating new key. "
                    "This should not happen in production! "
                    "Set LANGFLOW_CONNECTOR_ENCRYPTION_KEY environment variable."
                )
                key = Fernet.generate_key()

        return Fernet(key)

    def encrypt_token(self, token: str) -> str:
        """Encrypt an OAuth token.

        Args:
            token: Plain text token to encrypt

        Returns:
            Base64-encoded encrypted token
        """
        if not token:
            return ""

        try:
            encrypted = self.cipher_suite.encrypt(token.encode())
            return base64.urlsafe_b64encode(encrypted).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encrypt token: {e}")
            msg = "Token encryption failed"
            raise ValueError(msg) from e

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt an OAuth token.

        Args:
            encrypted_token: Base64-encoded encrypted token

        Returns:
            Decrypted plain text token
        """
        if not encrypted_token:
            return ""

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode("utf-8"))
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            msg = "Token decryption failed"
            raise ValueError(msg) from e

    def encrypt_config(self, config: dict[str, Any]) -> str:
        """Encrypt a configuration dictionary.

        Args:
            config: Configuration dictionary to encrypt

        Returns:
            Base64-encoded encrypted configuration
        """
        try:
            json_str = json.dumps(config, separators=(",", ":"))
            encrypted = self.cipher_suite.encrypt(json_str.encode())
            return base64.urlsafe_b64encode(encrypted).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encrypt config: {e}")
            msg = "Config encryption failed"
            raise ValueError(msg) from e

    def decrypt_config(self, encrypted_config: str) -> dict[str, Any]:
        """Decrypt a configuration dictionary.

        Args:
            encrypted_config: Base64-encoded encrypted configuration

        Returns:
            Decrypted configuration dictionary
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_config.encode("utf-8"))
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return json.loads(decrypted.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to decrypt config: {e}")
            msg = "Config decryption failed"
            raise ValueError(msg) from e


# Global encryption instance (singleton)
_encryption_instance: TokenEncryption | None = None


def get_encryption() -> TokenEncryption:
    """Get or create the global encryption instance.

    Returns:
        TokenEncryption instance
    """
    global _encryption_instance  # noqa: PLW0603
    if _encryption_instance is None:
        _encryption_instance = TokenEncryption()
    return _encryption_instance


def encrypt_sensitive_field(value: str) -> str:
    """Convenience function to encrypt a sensitive field.

    Args:
        value: Value to encrypt

    Returns:
        Encrypted value
    """
    return get_encryption().encrypt_token(value)


def decrypt_sensitive_field(encrypted_value: str) -> str:
    """Convenience function to decrypt a sensitive field.

    Args:
        encrypted_value: Encrypted value

    Returns:
        Decrypted value
    """
    return get_encryption().decrypt_token(encrypted_value)
