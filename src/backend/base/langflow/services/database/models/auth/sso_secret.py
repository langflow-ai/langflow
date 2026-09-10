"""Versioned at-rest encryption contract for SSO client secrets.

The ``sso_config.client_secret_encrypted`` column stores only envelopes emitted
by :func:`encrypt_sso_client_secret`; SSO read paths must never serialize or
otherwise return that column.

Envelope v1 is::

    lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:<nonce-b64url>:<ciphertext-b64url>

``ciphertext`` includes the 128-bit GCM authentication tag. The 256-bit AES key
is derived from the existing ``LANGFLOW_SECRET_KEY`` (``AuthSettings.SECRET_KEY``)
with HKDF-SHA256, a fixed domain-separation salt, and the distinct
``langflow/sso/client-secret/encryption`` info label. No additional setting or
environment variable is required.

Key/format rotation procedure:

1. Add a new envelope/KDF version while retaining decryption support for v1.
2. Re-encrypt every non-null column value internally, using the old version to
   decrypt and the new version to encrypt. Never expose plaintext through a read
   response or log.
3. Verify no old-version envelopes remain, then remove the old decryptor in a
   later release. A future KMS-backed key therefore changes envelope handling,
   not the database schema.
"""

from __future__ import annotations

import base64
import binascii
import os
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

_ENVELOPE_VERSION = "v1"
_KDF_VERSION = "hkdf-sha256-v1"
_ALGORITHM = "aes-256-gcm"
_PREFIX = "lf-sso"
_HEADER = f"{_PREFIX}:{_ENVELOPE_VERSION}:{_KDF_VERSION}:{_ALGORITHM}"
_AAD = _HEADER.encode()
_HKDF_SALT = b"langflow/sso/client-secret/hkdf-salt/v1"
_HKDF_INFO = b"langflow/sso/client-secret/encryption"
_NONCE_BYTES = 12
_TAG_BYTES = 16
_ENVELOPE_PARTS = 6
_HEADER_PARTS = 4
_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


class SSOSecretError(ValueError):
    """Raised when an SSO secret cannot be encoded or decoded safely."""


def _master_key(settings_service: SettingsService | None) -> bytes:
    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    secret_key = settings_service.auth_settings.SECRET_KEY.get_secret_value()
    if not secret_key:
        msg = "LANGFLOW_SECRET_KEY is required for SSO secret encryption"
        raise SSOSecretError(msg)
    return secret_key.encode()


def _derive_key(settings_service: SettingsService | None) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(_master_key(settings_service))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    if not value or any(character not in _BASE64URL_ALPHABET for character in value):
        msg = "Invalid base64url data in SSO secret envelope"
        raise SSOSecretError(msg)
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        msg = "Invalid base64url data in SSO secret envelope"
        raise SSOSecretError(msg) from exc


def _parse_envelope(envelope: str) -> tuple[bytes, bytes]:
    parts = envelope.split(":")
    if len(parts) != _ENVELOPE_PARTS or ":".join(parts[:_HEADER_PARTS]) != _HEADER:
        msg = "Unsupported SSO client-secret envelope or key-derivation version"
        raise SSOSecretError(msg)

    nonce = _decode(parts[4])
    ciphertext = _decode(parts[5])
    if len(nonce) != _NONCE_BYTES or len(ciphertext) < _TAG_BYTES:
        msg = "Invalid SSO client-secret envelope payload"
        raise SSOSecretError(msg)
    return nonce, ciphertext


def is_sso_client_secret_envelope(value: object) -> bool:
    """Return whether a value is a structurally valid current-version envelope."""
    if not isinstance(value, str):
        return False
    try:
        _parse_envelope(value)
    except SSOSecretError:
        return False
    return True


def encrypt_sso_client_secret(
    client_secret: str,
    settings_service: SettingsService | None = None,
) -> str:
    """Encrypt an SSO client secret into the current versioned envelope."""
    if not isinstance(client_secret, str):
        msg = "SSO client secret must be a string"
        raise TypeError(msg)
    if not client_secret.strip():
        msg = "SSO client secret must not be blank"
        raise SSOSecretError(msg)

    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_derive_key(settings_service)).encrypt(nonce, client_secret.encode(), _AAD)
    return f"{_HEADER}:{_encode(nonce)}:{_encode(ciphertext)}"


def decrypt_sso_client_secret(
    envelope: str,
    settings_service: SettingsService | None = None,
) -> str:
    """Decrypt a supported SSO client-secret envelope."""
    if not isinstance(envelope, str):
        msg = "SSO client-secret envelope must be a string"
        raise TypeError(msg)

    nonce, ciphertext = _parse_envelope(envelope)

    try:
        plaintext = AESGCM(_derive_key(settings_service)).decrypt(nonce, ciphertext, _AAD)
    except InvalidTag as exc:
        msg = "Unable to decrypt SSO client secret with LANGFLOW_SECRET_KEY"
        raise SSOSecretError(msg) from exc

    try:
        return plaintext.decode()
    except UnicodeDecodeError as exc:
        msg = "Decrypted SSO client secret is not valid UTF-8"
        raise SSOSecretError(msg) from exc
