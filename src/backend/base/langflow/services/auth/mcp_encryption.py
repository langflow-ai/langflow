"""MCP Authentication encryption utilities for secure credential storage."""

from typing import Any

from cryptography.fernet import InvalidToken
from lfx.log.logger import logger

from langflow.services.auth import utils as auth_utils
from langflow.services.deps import get_settings_service

# Fields that should be encrypted when stored
SENSITIVE_FIELDS = [
    "oauth_client_secret",
    "api_key",
]


def encrypt_auth_settings(auth_settings: dict[str, Any] | None) -> dict[str, Any] | None:
    """Encrypt sensitive fields in auth_settings dictionary.

    Args:
        auth_settings: Dictionary containing authentication settings

    Returns:
        Dictionary with sensitive fields encrypted, or None if input is None
    """
    if auth_settings is None:
        return None

    settings_service = get_settings_service()
    encrypted_settings = auth_settings.copy()

    for field in SENSITIVE_FIELDS:
        if encrypted_settings.get(field):
            try:
                field_to_encrypt = encrypted_settings[field]
                # Only encrypt if the value is not already encrypted
                # Try to decrypt first - if it fails, it's not encrypted
                try:
                    result = auth_utils.decrypt_api_key(field_to_encrypt, settings_service)
                    if not result:
                        msg = f"Failed to decrypt field {field}"
                        raise ValueError(msg)

                    # If decrypt succeeds, it's already encrypted
                    logger.debug(f"Field {field} is already encrypted")
                except (ValueError, TypeError, KeyError, InvalidToken):
                    # If decrypt fails, the value is plaintext and needs encryption
                    encrypted_value = auth_utils.encrypt_api_key(field_to_encrypt, settings_service)
                    encrypted_settings[field] = encrypted_value
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Failed to encrypt field {field}: {e}")
                raise

    return encrypted_settings


def decrypt_auth_settings(auth_settings: dict[str, Any] | None) -> dict[str, Any] | None:
    """Decrypt sensitive fields in auth_settings dictionary.

    Args:
        auth_settings: Dictionary containing encrypted authentication settings

    Returns:
        Dictionary with sensitive fields decrypted, or None if input is None
    """
    if auth_settings is None:
        return None

    settings_service = get_settings_service()
    decrypted_settings = auth_settings.copy()

    for field in SENSITIVE_FIELDS:
        if decrypted_settings.get(field):
            try:
                field_to_decrypt = decrypted_settings[field]

                decrypted_value = auth_utils.decrypt_api_key(field_to_decrypt, settings_service)
                if not decrypted_value:
                    msg = f"Failed to decrypt field {field}"
                    raise ValueError(msg)

                decrypted_settings[field] = decrypted_value
            except (ValueError, TypeError, KeyError, InvalidToken) as e:
                # If decryption fails, check if the value appears encrypted
                field_value = field_to_decrypt
                if isinstance(field_value, str) and field_value.startswith("gAAAAAB"):
                    # Value appears to be encrypted but decryption failed
                    logger.error(f"Failed to decrypt encrypted field {field}: {e}")
                    # For OAuth flows, we need the decrypted value, so raise the error
                    msg = f"Unable to decrypt {field}. Check encryption key configuration."
                    raise ValueError(msg) from e

                # Value doesn't appear encrypted, assume it's plaintext (backward compatibility)
                logger.debug(f"Field {field} appears to be plaintext, keeping original value")

    return decrypted_settings


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be encrypted.

    Args:
        value: String value to check

    Returns:
        True if the value appears to be encrypted (base64 Fernet token)
    """
    if not value:
        return False

    settings_service = get_settings_service()
    try:
        # Try to decrypt - if it succeeds, it's encrypted
        auth_utils.decrypt_api_key(value, settings_service)
    except (ValueError, TypeError, KeyError, InvalidToken):
        # If decryption fails, it's not encrypted
        return False
    else:
        return True
