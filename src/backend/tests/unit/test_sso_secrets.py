"""Tests for the versioned SSO client-secret encryption contract."""

from types import SimpleNamespace

import pytest
from langflow.services.database.models import (
    SSOSecretError,
    decrypt_sso_client_secret,
    encrypt_sso_client_secret,
)
from pydantic import SecretStr

_PLAINTEXT = "downstream-oidc-client-secret"
_DEFAULT_SECRET_KEY = "unit-test-langflow-secret-key-material"  # noqa: S105


def _settings(secret_key: str | None = None):
    return SimpleNamespace(auth_settings=SimpleNamespace(SECRET_KEY=SecretStr(secret_key or _DEFAULT_SECRET_KEY)))


def test_sso_client_secret_round_trip_uses_versioned_envelope():
    encrypted = encrypt_sso_client_secret(_PLAINTEXT, _settings())

    assert decrypt_sso_client_secret(encrypted, _settings()) == _PLAINTEXT
    assert _PLAINTEXT not in encrypted
    assert encrypted.startswith("lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:")


def test_sso_client_secret_defaults_to_existing_langflow_secret_key(monkeypatch):
    from langflow.services import deps

    settings = _settings()
    monkeypatch.setattr(deps, "get_settings_service", lambda: settings)

    encrypted = encrypt_sso_client_secret(_PLAINTEXT)

    assert decrypt_sso_client_secret(encrypted) == _PLAINTEXT


def test_sso_client_secret_encryption_uses_random_nonces():
    first = encrypt_sso_client_secret(_PLAINTEXT, _settings())
    second = encrypt_sso_client_secret(_PLAINTEXT, _settings())

    assert first != second
    assert decrypt_sso_client_secret(first, _settings()) == _PLAINTEXT
    assert decrypt_sso_client_secret(second, _settings()) == _PLAINTEXT


def test_sso_client_secret_rejects_wrong_langflow_secret_key():
    encrypted = encrypt_sso_client_secret(_PLAINTEXT, _settings("original-langflow-secret-key"))

    with pytest.raises(SSOSecretError, match="LANGFLOW_SECRET_KEY"):
        decrypt_sso_client_secret(encrypted, _settings("different-langflow-secret-key"))


def test_sso_client_secret_rejects_unknown_envelope_version():
    encrypted = encrypt_sso_client_secret(_PLAINTEXT, _settings())
    unknown_version = encrypted.replace(":v1:", ":v2:", 1)

    with pytest.raises(SSOSecretError, match="version"):
        decrypt_sso_client_secret(unknown_version, _settings())
