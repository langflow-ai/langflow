"""Unit tests for langflow.services.auth.external."""

from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from langflow.services.auth import external
from langflow.services.auth.exceptions import InvalidTokenError
from langflow.services.auth.external import (
    access_context_from_identity,
    decode_external_jwt,
    external_access_allows,
    extract_bearer_or_raw_token,
    extract_external_token,
    filter_actions_by_external_access_ceiling,
    get_current_external_access_context,
    identity_from_claims,
    resolve_external_identity,
    set_current_external_access_context,
)
from lfx.services.settings.auth import AuthSettings

_TEST_JWT_SECRET = "external-test-secret-with-enough-length"  # noqa: S105 # pragma: allowlist secret
_EXTERNAL_AUTH_HEADER = "X-External-Auth"
_EXTERNAL_AUTH_COOKIE = "external-session"
_OPAQUE_CREDENTIAL = "opaque-token"  # pragma: allowlist secret
_HEADER_CREDENTIAL = "header-token"  # pragma: allowlist secret


def _auth_settings(tmp_path, **overrides) -> AuthSettings:
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.EXTERNAL_AUTH_ENABLED = True
    settings.EXTERNAL_AUTH_PROVIDER = "test-provider"
    settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    settings.EXTERNAL_AUTH_TOKEN_HEADER = _EXTERNAL_AUTH_HEADER
    settings.EXTERNAL_AUTH_TOKEN_COOKIE = _EXTERNAL_AUTH_COOKIE
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


# ---------------------------------------------------------------------------
# extract_external_token / extract_bearer_or_raw_token
# ---------------------------------------------------------------------------


def test_extract_external_token_prefers_header_over_cookie(tmp_path):
    settings = _auth_settings(tmp_path)
    token = extract_external_token(
        {_EXTERNAL_AUTH_HEADER: f"Bearer {_HEADER_CREDENTIAL}"},
        {_EXTERNAL_AUTH_COOKIE: "cookie-token"},
        settings,
    )
    assert token == _HEADER_CREDENTIAL


def test_extract_external_token_returns_none_when_disabled(tmp_path):
    settings = _auth_settings(tmp_path, EXTERNAL_AUTH_ENABLED=False)
    assert extract_external_token({_EXTERNAL_AUTH_HEADER: "Bearer x"}, {}, settings) is None


def test_extract_external_token_falls_back_to_cookie(tmp_path):
    settings = _auth_settings(tmp_path)
    cookie_value = "cookie-token"  # pragma: allowlist secret
    token = extract_external_token({}, {_EXTERNAL_AUTH_COOKIE: cookie_value}, settings)
    assert token == cookie_value


def test_extract_bearer_or_raw_token_handles_variants():
    assert extract_bearer_or_raw_token(None) is None
    assert extract_bearer_or_raw_token("") is None
    assert extract_bearer_or_raw_token("   ") is None
    assert extract_bearer_or_raw_token("Bearer abc") == "abc"
    assert extract_bearer_or_raw_token("bearer abc") == "abc"
    assert extract_bearer_or_raw_token("opaque") == "opaque"


# ---------------------------------------------------------------------------
# decode_external_jwt (trusted-decode path)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_trusted_jwt_decode_validates_expiry(tmp_path):
    settings = _auth_settings(tmp_path)
    token = jwt.encode(
        {"sub": "expired-subject", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError, match="expired"):
        await decode_external_jwt(token, settings)


@pytest.mark.anyio
async def test_trusted_jwt_decode_validates_not_before(tmp_path):
    settings = _auth_settings(tmp_path)
    token = jwt.encode(
        {"sub": "future-subject", "nbf": datetime.now(timezone.utc) + timedelta(minutes=5)},
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError, match="not valid yet"):
        await decode_external_jwt(token, settings)


@pytest.mark.anyio
async def test_trusted_jwt_decode_returns_claims_when_valid(tmp_path):
    settings = _auth_settings(tmp_path)
    expected_sub = "subject-1"
    token = jwt.encode(
        {"sub": expected_sub, "preferred_username": "alice", "email": "alice@example.com"},
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    claims = await decode_external_jwt(token, settings)
    assert claims["sub"] == expected_sub
    assert claims["preferred_username"] == "alice"


@pytest.mark.anyio
async def test_decode_external_jwt_rejects_when_external_auth_disabled(tmp_path):
    settings = _auth_settings(tmp_path, EXTERNAL_AUTH_ENABLED=False)
    with pytest.raises(InvalidTokenError, match="not enabled"):
        await decode_external_jwt("anything", settings)


@pytest.mark.anyio
async def test_decode_external_jwt_requires_jwks_when_not_trusted(tmp_path):
    settings = _auth_settings(
        tmp_path,
        EXTERNAL_AUTH_TRUSTED_JWT_DECODE=False,
        EXTERNAL_AUTH_JWKS_URL=None,
    )
    with pytest.raises(InvalidTokenError, match="EXTERNAL_AUTH_JWKS_URL"):
        await decode_external_jwt("anything", settings)


# ---------------------------------------------------------------------------
# decode_external_jwt (JWKS path)
# ---------------------------------------------------------------------------

_JWKS_URL = "https://idp.example.com/.well-known/jwks.json"


def _jwks_settings(tmp_path) -> AuthSettings:
    return _auth_settings(
        tmp_path,
        EXTERNAL_AUTH_TRUSTED_JWT_DECODE=False,
        EXTERNAL_AUTH_JWKS_URL=_JWKS_URL,
        EXTERNAL_AUTH_ALGORITHMS="HS256",
    )


def _symmetric_jwk(secret: str, kid: str) -> dict:
    return {
        "kty": "oct",
        "alg": "HS256",
        "kid": kid,
        "k": base64.urlsafe_b64encode(secret.encode()).rstrip(b"=").decode(),
    }


def _install_fake_jwks_endpoint(monkeypatch, payloads: list[dict]) -> list[str]:
    """Serve payloads[i] for the i-th JWKS fetch (last payload repeats); returns the call log."""
    calls: list[str] = []

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url):
            calls.append(url)
            return _FakeResponse(payloads[min(len(calls) - 1, len(payloads) - 1)])

    monkeypatch.setattr(external.httpx, "AsyncClient", _FakeAsyncClient)
    return calls


@pytest.mark.anyio
async def test_jwks_decode_verifies_signature(tmp_path, monkeypatch):
    settings = _jwks_settings(tmp_path)
    monkeypatch.setattr(external, "_jwks_cache", {})
    _install_fake_jwks_endpoint(monkeypatch, [{"keys": [_symmetric_jwk(_TEST_JWT_SECRET, kid="key-1")]}])

    token = jwt.encode({"sub": "subject-1"}, _TEST_JWT_SECRET, algorithm="HS256", headers={"kid": "key-1"})
    claims = await decode_external_jwt(token, settings)
    assert claims["sub"] == "subject-1"

    wrong_secret = "another-secret-that-did-not-sign-the-jwks-key"  # noqa: S105 # pragma: allowlist secret
    tampered = jwt.encode({"sub": "subject-1"}, wrong_secret, algorithm="HS256", headers={"kid": "key-1"})
    with pytest.raises(InvalidTokenError, match="validation failed"):
        await decode_external_jwt(tampered, settings)


@pytest.mark.anyio
async def test_jwks_refetches_when_kid_is_newer_than_cache(tmp_path, monkeypatch):
    """IdP key rotation: an unknown kid forces one cache-busting JWKS refetch."""
    settings = _jwks_settings(tmp_path)
    old_jwks = {"keys": [_symmetric_jwk(_TEST_JWT_SECRET, kid="old-key")]}
    new_jwks = {"keys": [_symmetric_jwk(_TEST_JWT_SECRET, kid="new-key")]}
    # Cached entry is still valid but old enough to be past the refresh rate limit.
    fetched_at = time.monotonic() - external.JWKS_MIN_REFRESH_INTERVAL_SECONDS - 1
    monkeypatch.setattr(external, "_jwks_cache", {_JWKS_URL: (fetched_at + external.JWKS_CACHE_TTL_SECONDS, old_jwks)})
    calls = _install_fake_jwks_endpoint(monkeypatch, [new_jwks])

    token = jwt.encode({"sub": "rotated"}, _TEST_JWT_SECRET, algorithm="HS256", headers={"kid": "new-key"})
    claims = await decode_external_jwt(token, settings)

    assert claims["sub"] == "rotated"
    assert calls == [_JWKS_URL]


@pytest.mark.anyio
async def test_jwks_refresh_is_rate_limited_for_unknown_kid(tmp_path, monkeypatch):
    """A freshly fetched JWKS is not refetched for an unknown kid (anti-hammering)."""
    settings = _jwks_settings(tmp_path)
    jwks = {"keys": [_symmetric_jwk(_TEST_JWT_SECRET, kid="key-1")]}
    monkeypatch.setattr(
        external, "_jwks_cache", {_JWKS_URL: (time.monotonic() + external.JWKS_CACHE_TTL_SECONDS, jwks)}
    )
    calls = _install_fake_jwks_endpoint(monkeypatch, [jwks])

    token = jwt.encode({"sub": "nope"}, _TEST_JWT_SECRET, algorithm="HS256", headers={"kid": "unknown-key"})
    with pytest.raises(InvalidTokenError, match="not found in JWKS"):
        await decode_external_jwt(token, settings)

    assert calls == []


# ---------------------------------------------------------------------------
# identity_from_claims / resolve_external_identity
# ---------------------------------------------------------------------------


def test_identity_from_claims_uses_configured_mapping(tmp_path):
    settings = _auth_settings(tmp_path)
    identity = identity_from_claims(
        {
            "sub": "subject-1",
            "preferred_username": "alice",
            "email": "alice@example.com",
            "name": "Alice",
        },
        settings,
    )
    assert identity.provider == "test-provider"
    assert identity.subject == "subject-1"
    assert identity.username == "alice"
    assert identity.email == "alice@example.com"
    assert identity.name == "Alice"


def test_identity_from_claims_requires_subject(tmp_path):
    settings = _auth_settings(tmp_path)
    with pytest.raises(InvalidTokenError, match="missing required claim"):
        identity_from_claims({"preferred_username": "no-sub"}, settings)


def test_identity_from_claims_falls_back_to_synthesized_username(tmp_path):
    settings = _auth_settings(tmp_path)
    identity = identity_from_claims({"sub": "subject-9"}, settings)
    assert identity.username.startswith("test-provider-")
    assert identity.email is None
    assert identity.name is None


def test_external_access_context_uses_configured_claim_mapping(tmp_path):
    settings = _auth_settings(
        tmp_path,
        EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=True,
        EXTERNAL_AUTH_ACCESS_CLAIM="openrag_mode",
        EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING='{"can_view":"viewer","can_edit":"editor"}',
    )
    identity = identity_from_claims({"sub": "subject-1", "openrag_mode": "can_edit"}, settings)

    context = access_context_from_identity(identity, settings)

    assert context is not None
    assert context.level == "editor"
    assert external_access_allows("write", context)
    assert external_access_allows("execute", context)
    assert not external_access_allows("delete", context)


def test_external_access_context_defaults_to_viewer_for_missing_claim(tmp_path):
    settings = _auth_settings(
        tmp_path,
        EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=True,
        EXTERNAL_AUTH_ACCESS_CLAIM="openrag_mode",
    )
    identity = identity_from_claims({"sub": "subject-1"}, settings)

    context = access_context_from_identity(identity, settings)

    assert context is not None
    assert context.level == "viewer"
    assert external_access_allows("read", context)
    assert not external_access_allows("write", context)


def test_filter_actions_by_external_access_ceiling_uses_request_context():
    set_current_external_access_context(
        external.ExternalAccessContext(provider="test-provider", subject="subject-1", level="viewer")
    )
    try:
        assert filter_actions_by_external_access_ceiling(["read", "write", "delete"]) == ["read"]
        assert get_current_external_access_context() is not None
    finally:
        set_current_external_access_context(None)


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
async def test_resolve_external_identity_default_uses_jwt(tmp_path):
    settings = _auth_settings(tmp_path)
    token = jwt.encode(
        {
            "sub": "subject-1",
            "preferred_username": "bob",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    identity = await resolve_external_identity(token, settings)
    assert identity.subject == "subject-1"
    assert identity.username == "bob"
