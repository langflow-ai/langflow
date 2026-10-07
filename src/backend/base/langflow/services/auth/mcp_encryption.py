"""MCP Authentication encryption utilities for secure credential storage."""

from copy import deepcopy
from typing import Any

from cryptography.fernet import InvalidToken
from lfx.log.logger import logger

from langflow.services.auth import utils as auth_utils

# Fields that should be encrypted when stored
SENSITIVE_FIELDS = [
    "oauth_client_secret",
    "api_key",
]

# Sub-maps of an ``mcpServers`` entry whose *values* carry secrets (API keys,
# bearer tokens) and must be encrypted at rest in the mcp_server table.
MCP_SECRET_CONFIG_MAPS = ("env", "headers")
MCP_CONFIG_VALUE_MASK = "********"


def encrypt_auth_settings(auth_settings: dict[str, Any] | None) -> dict[str, Any] | None:
    """Encrypt sensitive fields in auth_settings dictionary.

    Args:
        auth_settings: Dictionary containing authentication settings

    Returns:
        Dictionary with sensitive fields encrypted, or None if input is None
    """
    if auth_settings is None:
        return None

    encrypted_settings = auth_settings.copy()

    for field in SENSITIVE_FIELDS:
        if encrypted_settings.get(field):
            try:
                field_to_encrypt = encrypted_settings[field]
                # Only encrypt if the value is not already encrypted
                # Check if it's already encrypted using is_encrypted helper
                if is_encrypted(field_to_encrypt):
                    logger.debug(f"Field {field} is already encrypted")
                else:
                    # Not encrypted, encrypt it
                    encrypted_value = auth_utils.encrypt_api_key(field_to_encrypt)
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

    decrypted_settings = auth_settings.copy()

    for field in SENSITIVE_FIELDS:
        if decrypted_settings.get(field):
            try:
                field_to_decrypt = decrypted_settings[field]

                decrypted_value = auth_utils.decrypt_api_key(field_to_decrypt)
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


def _header_arg_positions(args: list[str] | None) -> dict[str, list[int]]:
    """Locate values in repeated mcp-proxy ``--headers NAME VALUE`` options."""
    positions: dict[str, list[int]] = {}
    index = 0
    while args and index + 2 < len(args):
        if args[index] == "--headers":
            positions.setdefault(args[index + 1].casefold(), []).append(index + 2)
            index += 3
        else:
            index += 1
    return positions


def encrypt_mcp_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Encrypt secret-bearing values inside an ``mcpServers`` entry for storage.

    Encrypts every value in the entry's ``env`` and ``headers`` maps (where API
    keys and bearer tokens live), plus values in mcp-proxy ``--headers NAME VALUE``
    arguments. Leaves structural fields and other arguments untouched. Idempotent:
    already-encrypted values are left as-is, so re-encrypting a stored config is a
    no-op. Returns a copy; the input is not mutated.
    """
    if not config:
        return config

    encrypted = deepcopy(config)
    for map_name in MCP_SECRET_CONFIG_MAPS:
        values = encrypted.get(map_name)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if isinstance(value, str) and value and not is_encrypted(value):
                values[key] = auth_utils.encrypt_api_key(value)
    args = encrypted.get("args")
    for positions in _header_arg_positions(args).values():
        for index in positions:
            if args[index] and not is_encrypted(args[index]):
                args[index] = auth_utils.encrypt_api_key(args[index])
    return encrypted


def decrypt_mcp_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Decrypt an ``mcpServers`` entry read from storage into a runnable config.

    Inverse of :func:`encrypt_mcp_config`. ``decrypt_api_key`` returns non-token
    input unchanged, so plaintext values (e.g. rows written before encryption
    shipped, or imported legacy files) pass through untouched for backward
    compatibility. Returns a copy; the input is not mutated.
    """
    if not config:
        return config

    decrypted = deepcopy(config)
    for map_name in MCP_SECRET_CONFIG_MAPS:
        values = decrypted.get(map_name)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if isinstance(value, str) and value:
                values[key] = auth_utils.decrypt_api_key(value)
    args = decrypted.get("args")
    for positions in _header_arg_positions(args).values():
        for index in positions:
            if args[index]:
                args[index] = auth_utils.decrypt_api_key(args[index])
    return decrypted


def redact_mcp_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Copy a public MCP config without disclosing credential-bearing map values."""
    if not config:
        return config
    redacted = deepcopy(config)
    for map_name in MCP_SECRET_CONFIG_MAPS:
        values = redacted.get(map_name)
        if isinstance(values, dict):
            for key, value in values.items():
                if value:
                    values[key] = MCP_CONFIG_VALUE_MASK
    args = redacted.get("args")
    for positions in _header_arg_positions(args).values():
        for index in positions:
            if args[index]:
                args[index] = MCP_CONFIG_VALUE_MASK
    return redacted


def restore_mcp_config_secrets(config: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve unchanged editor masks against the latest config before encrypting.

    Each supplied map still replaces its predecessor, so removing a key or sending
    an empty map clears credentials. A mask may only preserve an existing key.
    Header argument masks match names and occurrences, rather than positions.
    Changing duplicate counts is ambiguous, so it requires replacement values.
    """
    restored = deepcopy(config)
    for map_name in MCP_SECRET_CONFIG_MAPS:
        values = restored.get(map_name)
        if not isinstance(values, dict):
            continue
        previous_values = (existing or {}).get(map_name) or {}
        for key, value in values.items():
            if value == MCP_CONFIG_VALUE_MASK:
                if key not in previous_values:
                    msg = "A redacted MCP credential can only preserve an existing value."
                    raise ValueError(msg)
                values[key] = previous_values[key]
    args = restored.get("args")
    if isinstance(args, list) and MCP_CONFIG_VALUE_MASK in args:
        previous_args = (existing or {}).get("args") or []
        previous_positions = _header_arg_positions(previous_args)
        resolved_positions: set[int] = set()
        for name, positions in _header_arg_positions(args).items():
            old_positions = previous_positions.get(name, [])
            for occurrence, index in enumerate(positions):
                if args[index] != MCP_CONFIG_VALUE_MASK:
                    continue
                if len(positions) != len(old_positions):
                    msg = "Redacted MCP header arguments require unchanged header names and duplicate counts."
                    raise ValueError(msg)
                args[index] = previous_args[old_positions[occurrence]]
                resolved_positions.add(index)
        if any(value == MCP_CONFIG_VALUE_MASK and index not in resolved_positions for index, value in enumerate(args)):
            msg = "A redacted MCP argument can only preserve an existing header value."
            raise ValueError(msg)
    return restored


def is_encrypted(value: str) -> bool:  # pragma: allowlist secret
    """Check if a value appears to be encrypted.

    Args:
        value: String value to check

    Returns:
        True if the value appears to be encrypted (base64 Fernet token)
    """
    if not value:
        return False

    try:
        # Try to decrypt - if it succeeds and returns a different value, it's encrypted
        decrypted = auth_utils.decrypt_api_key(value)
        # If decryption returns empty string, it's encrypted with wrong key
        if not decrypted:
            return True
        # If it returns a different value, it's successfully decrypted (was encrypted)
        # If it returns the same value, something unexpected happened
        return decrypted != value  # noqa: TRY300
    except (ValueError, TypeError, KeyError, InvalidToken):
        # If decryption fails with exception, assume it's encrypted but can't be decrypted
        return True
