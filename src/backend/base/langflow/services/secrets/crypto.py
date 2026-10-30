"""Explicit-key cryptography extracted from the offline key migration script.

These helpers raise on failed decryption; they never call the runtime auth
service, whose empty-string fallback cannot verify a rotation.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import random

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from langflow.services.auth.mcp_encryption import MCP_SECRET_CONFIG_MAPS, _argv_secret_positions

MINIMUM_KEY_LENGTH = 32
# Holds the new key from just before the database commit until it replaces secret_key.
PENDING_KEY_FILENAME = "secret_key.new"
# Columns that hold a single Fernet token: (table, primary key, column, description).
FERNET_TOKEN_COLUMNS = [
    # Authentication uses apikey.api_key_hash, but the stored value is lost if not rotated.
    ("apikey", "id", "api_key", "stored API key values"),
    ("deployment_provider_account", "id", "api_key", "deployment provider API keys"),
    ("connection_secret", "connection_id", "encrypted_payload", "connection credentials"),
    ("trigger", "id", "signing_secret_encrypted", "trigger signing secrets"),
]
SENSITIVE_AUTH_FIELDS = ["oauth_client_secret", "api_key"]
FERNET_VERSION_BYTE = 0x80
FERNET_MIN_TOKEN_BYTES = 73  # version + timestamp + IV + one AES block + HMAC
# Must match langflow.services.variable.constants.CREDENTIAL_TYPE
CREDENTIAL_TYPE = "Credential"
SSO_ENVELOPE_HEADER = "lf-sso:v1:hkdf-sha256-v1:aes-256-gcm"
SSO_AAD = SSO_ENVELOPE_HEADER.encode()
SSO_HKDF_SALT = b"langflow/sso/client-secret/hkdf-salt/v1"
SSO_HKDF_INFO = b"langflow/sso/client-secret/encryption"
SSO_NONCE_BYTES = 12
SSO_TAG_BYTES = 16
SSO_ENVELOPE_PARTS = 6
SSO_HEADER_PARTS = 4
SSO_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
RECEIPT_FINGERPRINT_CONTEXT = b"langflow/secret-rotation/root-fingerprint/v1"


def receipt_fingerprint(key: str) -> str:
    """Identify a root without exposing the Fernet key derived from short roots."""
    return hmac.new(RECEIPT_FINGERPRINT_CONTEXT, key.encode(), hashlib.sha256).hexdigest()


def key_fingerprint(key: str) -> str:
    """Identify a key without revealing it: the first 12 hex characters of its SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def ensure_valid_key(s: str) -> bytes:
    """Convert a secret key string to the Fernet key the app encrypts with.

    For keys shorter than MINIMUM_KEY_LENGTH (32), the key is the SHA-256 digest
    of the secret, as the app has done since 1.10.1. For longer keys, pads with
    '=' to ensure valid base64 encoding.

    NOTE: This mirrors langflow.services.auth.utils.ensure_fernet_key.
    Keep in sync if encryption logic changes.
    """
    if len(s) < MINIMUM_KEY_LENGTH:
        return base64.urlsafe_b64encode(hashlib.sha256(s.encode()).digest())
    padding_needed = -len(s) % 4
    return (s + "=" * padding_needed).encode()


def legacy_short_key(s: str) -> bytes:
    """The pre-1.10.1 key for a short secret, used only to read values written back then.

    Mirrors langflow.services.auth.utils._ensure_legacy_fernet_key.
    """
    legacy_random = random.Random(s)  # noqa: S311 - reproduces a historical derivation, never encrypts
    return base64.urlsafe_b64encode(bytes(legacy_random.getrandbits(8) for _ in range(32)))


def decrypt_with_key(encrypted: str, key: str) -> str:
    """Decrypt data with the given key, reading pre-1.10.1 values of short keys too."""
    fernet = Fernet(ensure_valid_key(key))
    if len(key) < MINIMUM_KEY_LENGTH:
        fernet = MultiFernet([fernet, Fernet(legacy_short_key(key))])
    return fernet.decrypt(encrypted.encode()).decode()


def encrypt_with_key(plaintext: str, key: str) -> str:
    """Encrypt data with the given key."""
    fernet = Fernet(ensure_valid_key(key))
    return fernet.encrypt(plaintext.encode()).decode()


def migrate_value(encrypted: str, old_key: str, new_key: str) -> str | None:
    """Decrypt with old key and re-encrypt with new key.

    Returns:
        The re-encrypted value, or None if decryption fails (invalid key or corrupted data).
    """
    try:
        plaintext = decrypt_with_key(encrypted, old_key)
        return encrypt_with_key(plaintext, new_key)
    # ValueError: the old key cannot build a Fernet, so no value can be under it.
    except (InvalidToken, ValueError):
        return None


def _derive_sso_key(master_key: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SSO_HKDF_SALT,
        info=SSO_HKDF_INFO,
    ).derive(master_key.encode())


def _decode_sso_envelope(envelope: str) -> tuple[bytes, bytes]:
    parts = envelope.split(":")
    if len(parts) != SSO_ENVELOPE_PARTS or ":".join(parts[:SSO_HEADER_PARTS]) != SSO_ENVELOPE_HEADER:
        msg = "Unsupported SSO client-secret envelope"
        raise ValueError(msg)
    decoded_payloads: list[bytes] = []
    for value in parts[4:]:
        if not value or any(character not in SSO_BASE64URL_ALPHABET for character in value):
            msg = "Invalid base64url data in SSO client-secret envelope"
            raise ValueError(msg)
        try:
            decoded_payloads.append(base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True))
        except (binascii.Error, ValueError) as exc:
            msg = "Invalid base64url data in SSO client-secret envelope"
            raise ValueError(msg) from exc
    nonce, ciphertext = decoded_payloads
    if len(nonce) != SSO_NONCE_BYTES or len(ciphertext) < SSO_TAG_BYTES:
        msg = "Invalid SSO client-secret envelope payload"
        raise ValueError(msg)
    return nonce, ciphertext


def decrypt_sso_secret_with_key(envelope: str, key: str) -> str:
    """Decrypt an SSO client-secret envelope with an explicit master key."""
    nonce, ciphertext = _decode_sso_envelope(envelope)
    plaintext = AESGCM(_derive_sso_key(key)).decrypt(nonce, ciphertext, SSO_AAD)
    return plaintext.decode()


def encrypt_sso_secret_with_key(plaintext: str, key: str) -> str:
    """Encrypt an SSO client secret using the application's current envelope format."""
    nonce = os.urandom(SSO_NONCE_BYTES)
    ciphertext = AESGCM(_derive_sso_key(key)).encrypt(nonce, plaintext.encode(), SSO_AAD)
    encoded_nonce = base64.urlsafe_b64encode(nonce).rstrip(b"=").decode()
    encoded_ciphertext = base64.urlsafe_b64encode(ciphertext).rstrip(b"=").decode()
    return f"{SSO_ENVELOPE_HEADER}:{encoded_nonce}:{encoded_ciphertext}"


def migrate_sso_secret(envelope: str, old_key: str, new_key: str) -> str | None:
    """Rewrap an SSO client-secret envelope under a replacement master key."""
    try:
        plaintext = decrypt_sso_secret_with_key(envelope, old_key)
        return encrypt_sso_secret_with_key(plaintext, new_key)
    except (InvalidTag, UnicodeDecodeError, ValueError):
        return None


def migrate_auth_settings(auth_settings: dict, old_key: str, new_key: str) -> tuple[dict, list[str]]:
    """Re-encrypt sensitive fields in auth_settings dict.

    Returns:
        Tuple of (migrated_settings, failed_fields) where failed_fields contains
        names of fields that could not be decrypted with the old key.
    """
    result = auth_settings.copy()
    failed_fields = []
    for field in SENSITIVE_AUTH_FIELDS:
        if result.get(field):
            new_value = migrate_value(result[field], old_key, new_key)
            if new_value:
                result[field] = new_value
            else:
                failed_fields.append(field)
    return result, failed_fields


def looks_like_fernet_token(value: object) -> bool:
    """Tell a Fernet token from a plaintext value without knowing the key.

    mcp_server.config can hold plaintext values written before encryption
    shipped, and those must be left alone rather than counted as failures.
    """
    if not isinstance(value, str):
        return False
    try:
        raw = base64.urlsafe_b64decode(value.encode() + b"=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return False
    return len(raw) >= FERNET_MIN_TOKEN_BYTES and raw[0] == FERNET_VERSION_BYTE


def migrate_mcp_config(config: dict, old_key: str, new_key: str) -> tuple[dict, list[str]]:
    """Re-encrypt the secret values inside an mcp_server.config entry.

    Returns:
        Tuple of (migrated_config, failed_fields) where failed_fields names
        values that look encrypted but cannot be decrypted with the old key.
    """
    result = json.loads(json.dumps(config))
    failed_fields = []
    for map_name in MCP_SECRET_CONFIG_MAPS:
        values = result.get(map_name)
        if not isinstance(values, dict):
            continue
        for name, value in values.items():
            if not isinstance(value, str) or not value or not looks_like_fernet_token(value):
                continue
            new_value = migrate_value(value, old_key, new_key)
            if new_value:
                values[name] = new_value
            else:
                failed_fields.append(f"{map_name}.{name}")
    args = result.get("args")
    for position in _argv_secret_positions(args):
        if not looks_like_fernet_token(args[position]):
            continue
        new_value = migrate_value(args[position], old_key, new_key)
        if new_value:
            args[position] = new_value
        else:
            failed_fields.append(f"args[{position}]")
    return result, failed_fields
