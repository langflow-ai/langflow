"""Provider OAuth hooks keep state, token hosts, and response checks shared."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from langflow.services.connection.oauth import adapter, providers
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration


@pytest.fixture
def oauth(monkeypatch):
    async def parse(_registration, body, *, refresh):
        return body["credential"], None if refresh else {"id": "account-1", "tenant_id": "tenant-1"}

    oauth = adapter.OAuthAdapter(
        endpoints=lambda _registration: ("https://auth.pilot.example/authorize", "https://auth.pilot.example/token"),
        allowed_origins=("https://auth.pilot.example",),
        validate_registration=lambda _registration: None,
        parse_token=parse,
        token_encoding="json",  # noqa: S106 - serialization format
        authorization_params=lambda _registration: {"audience": "pilot", "state": "untrusted-override"},
    )
    monkeypatch.setattr(adapter, "provider_adapter", lambda provider: oauth if provider == "pilot" else None)
    return oauth


def _registration(**overrides):
    return OAuthRegistration(
        provider="pilot",
        client_id="pilot-client",
        client_secret="synthetic-client-secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="https://langflow.example/api/v1/connections/oauth/pilot/callback",
        scopes=["items:read"],
        **overrides,
    )


@pytest.mark.usefixtures("oauth")
def test_custom_authorization_preserves_shared_state_pkce_and_redirect():
    registration = _registration()
    url = providers.authorization_url(registration, state="trusted-state", verifier="verifier", scopes=["items:read"])
    query = parse_qs(urlsplit(url).query)
    assert query["state"] == ["trusted-state"]
    assert query["redirect_uri"] == [registration.redirect_uri]
    assert query["code_challenge"] == [providers.challenge("verifier")]
    assert query["scope"] == ["items:read"]
    assert query["audience"] == ["pilot"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://auth.pilot.example/token",
        "https://attacker.example/token",
        "https://owner:secret@auth.pilot.example/token",  # pragma: allowlist secret
        "https://auth.pilot.example/token?credential=value",
    ],
)
def test_custom_endpoints_reject_untrusted_credential_destinations(oauth, endpoint):
    with pytest.raises(OAuthError, match="configured HTTPS origins"):
        replace(oauth, endpoints=lambda _registration: (endpoint, endpoint)).checked_endpoints(SimpleNamespace())


def test_unknown_provider_never_falls_back_to_slack(monkeypatch):
    monkeypatch.setattr(adapter, "provider_adapter", lambda _provider: None)
    with pytest.raises(OAuthError, match="unavailable"):
        providers.endpoints(SimpleNamespace(provider="unknown"))


@pytest.mark.usefixtures("oauth")
async def test_json_exchange_uses_shared_token_validation_and_refresh(monkeypatch):
    calls = []

    async def request(url, data, **kwargs):
        calls.append((url, data, kwargs))
        return {
            "credential": {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
                "expires_in": 3600,
                "scope": "items:read",
            }
        }

    monkeypatch.setattr(providers, "_request", request)
    payload, scopes, account = await providers.exchange(
        _registration(), code="code", verifier="verifier", previous_scopes=["items:read", "items:write"]
    )
    assert calls[0][0] == "https://auth.pilot.example/token"
    assert calls[0][1]["code_verifier"] == "verifier"
    assert calls[0][2]["json_body"] is True
    assert payload["expires_at"] is not None
    assert scopes == ["items:read"]
    assert account == {"id": "account-1", "tenant_id": "tenant-1"}
    await providers.exchange(_registration(), refresh_token="synthetic-refresh", previous_scopes=scopes)  # noqa: S106
    assert calls[1][1]["grant_type"] == "refresh_token"
    assert "code_verifier" not in calls[1][1]


@pytest.mark.usefixtures("oauth")
async def test_custom_token_parser_cannot_bypass_expiry_or_tenant_validation(monkeypatch):
    async def request(*_args, **_kwargs):
        return {"credential": {"access_token": "synthetic-access", "expires_in": -1, "scope": "items:read"}}

    monkeypatch.setattr(providers, "_request", request)
    with pytest.raises(OAuthError, match="invalid token expiry"):
        await providers.exchange(_registration(), code="code", previous_scopes=["items:read"])
    with pytest.raises(OAuthError, match="tenant restriction"):
        await providers.exchange(
            _registration(allowed_tenants=["other-tenant"]), code="code", previous_scopes=["items:read"]
        )


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize(
    "result",
    [
        KeyError("private-provider-value"),
        TypeError("private-provider-value"),
        None,
        {},
        [],
        ({},),
        ({}, None, None),
        [{"access_token": "synthetic-access"}, None],
        (None, None),
        ({"access_token": "synthetic-access"}, "invalid"),
    ],
    ids=[
        "missing-key",
        "wrong-type",
        "none",
        "mapping",
        "empty-list",
        "short-tuple",
        "long-tuple",
        "list",
        "token",
        "account",
    ],
)
async def test_custom_token_parser_failures_are_sanitized(oauth, monkeypatch, refresh, result):
    async def request(*_args, **_kwargs):
        return {"credential": {"access_token": "synthetic-access"}}

    async def parse(*_args, **_kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(providers, "_request", request)
    monkeypatch.setattr(adapter, "provider_adapter", lambda _provider: replace(oauth, parse_token=parse))
    kwargs = {"refresh_token": "synthetic-refresh"} if refresh else {"code": "code"}
    with pytest.raises(OAuthError) as caught:
        await providers.exchange(_registration(), previous_scopes=["items:read"], **kwargs)
    assert caught.value.reason == "provider-unavailable"
    assert "private-provider-value" not in str(caught.value)


@pytest.mark.parametrize("error", [OAuthError("Authored rejection."), asyncio.CancelledError()])
async def test_custom_token_parser_preserves_authored_errors_and_cancellation(oauth, monkeypatch, error):
    async def request(*_args, **_kwargs):
        return {}

    async def parse(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(providers, "_request", request)
    monkeypatch.setattr(adapter, "provider_adapter", lambda _provider: replace(oauth, parse_token=parse))
    with pytest.raises(type(error)) as caught:
        await providers.exchange(_registration(), code="code", previous_scopes=[])
    assert caught.value is error
