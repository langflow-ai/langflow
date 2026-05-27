from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from langflow.services.auth.exceptions import InvalidTokenError
from langflow.services.auth.external import decode_external_jwt, extract_external_token, resolve_external_identity
from lfx.services.settings.auth import AuthSettings

_TEST_JWT_SECRET = "external-test-secret-for-jwt-tests"  # noqa: S105
_EXTERNAL_AUTH_HEADER = "X-External-Auth"
_EXTERNAL_AUTH_COOKIE = "external-session"
_OPAQUE_CREDENTIAL = "opaque-token"
_HEADER_CREDENTIAL = "header-token"


def _auth_settings(tmp_path) -> AuthSettings:
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.EXTERNAL_AUTH_ENABLED = True
    settings.EXTERNAL_AUTH_PROVIDER = "test-provider"
    settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    settings.EXTERNAL_AUTH_TOKEN_HEADER = _EXTERNAL_AUTH_HEADER
    settings.EXTERNAL_AUTH_TOKEN_COOKIE = _EXTERNAL_AUTH_COOKIE
    return settings


@pytest.mark.anyio
async def test_resolve_external_identity_uses_configured_resolver(tmp_path, monkeypatch):
    settings = _auth_settings(tmp_path)
    settings.EXTERNAL_AUTH_IDENTITY_RESOLVER = "tests.fake:resolver"

    async def resolver(token, auth_settings):
        assert token == _OPAQUE_CREDENTIAL
        assert auth_settings is settings
        return {
            "sub": "opaque-subject",
            "preferred_username": "opaque-user",
            "email": "opaque@example.com",
            "name": "Opaque User",
        }

    from lfx.services import config_discovery

    def load_resolver(import_path, *, object_kind, object_key):
        assert import_path == settings.EXTERNAL_AUTH_IDENTITY_RESOLVER
        assert object_kind == "external auth resolver"
        assert object_key == "EXTERNAL_AUTH_IDENTITY_RESOLVER"
        return resolver

    monkeypatch.setattr(config_discovery, "load_object_from_import_path", load_resolver)

    identity = await resolve_external_identity(_OPAQUE_CREDENTIAL, settings)

    assert identity.provider == "test-provider"
    assert identity.subject == "opaque-subject"
    assert identity.username == "opaque-user"
    assert identity.email == "opaque@example.com"
    assert identity.name == "Opaque User"


@pytest.mark.anyio
async def test_trusted_jwt_decode_validates_time_claims(tmp_path):
    settings = _auth_settings(tmp_path)
    token = jwt.encode(
        {
            "sub": "expired-subject",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError, match="expired"):
        await decode_external_jwt(token, settings)


def test_extract_external_token_prefers_header_over_cookie(tmp_path):
    settings = _auth_settings(tmp_path)

    token = extract_external_token(
        {_EXTERNAL_AUTH_HEADER: f"Bearer {_HEADER_CREDENTIAL}"},
        {_EXTERNAL_AUTH_COOKIE: "cookie-token"},
        settings,
    )

    assert token == _HEADER_CREDENTIAL
