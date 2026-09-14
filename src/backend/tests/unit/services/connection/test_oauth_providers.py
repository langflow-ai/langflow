"""Provider protocol differences, configuration restrictions, and redaction."""

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from langflow.services.connection.oauth import providers
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration, OAuthSettings
from lfx.log.logger import _build_redact_processor
from lfx.utils.env_var_security import safe_getenv
from pydantic import SecretStr, ValidationError

_INVALID_AUTH_ORIGIN = "https://user:password@localhost"  # pragma: allowlist secret - invalid URL test


def config(**kwargs):
    return OAuthRegistration.model_validate(
        {
            "provider": "google",
            "client_id": "public-id",
            "client_type": "public",
            "context": "desktop",
            "redirect_uri": "http://localhost/api/v1/connections/oauth/google/callback",
            "scopes": ["read"],
            **kwargs,
        }
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"redirect_uri": "http://evil.example/api/v1/connections/oauth/google/callback"},
        {"redirect_uri": "http://localhost.evil.example/api/v1/connections/oauth/google/callback"},
        {"redirect_uri": "http://localhost/api/v1/connections/oauth/google/callback?next=elsewhere"},
        {"redirect_uri": _INVALID_AUTH_ORIGIN + "/api/v1/connections/oauth/google/callback"},
        {"client_secret": "should-not-be-embedded"},  # pragma: allowlist secret - deliberately invalid test fixture
        {"profile": "bot"},
        {"context": "self_managed", "owner": "langflow"},
        {"allowed_tenants": ["example.com"]},
    ],
)
def test_invalid_registrations_fail_closed(overrides):
    with pytest.raises(ValidationError):
        config(**overrides)


def test_customer_default_and_hosted_configuration_gate(monkeypatch):
    monkeypatch.delenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", raising=False)
    assert OAuthSettings().context == "self_managed"
    value = {
        "provider": "google",
        "client_id": "hosted-client",
        "client_secret": "registration-secret",  # pragma: allowlist secret - deliberately invalid test fixture
        "owner": "langflow",
        "context": "hosted",
        "redirect_uri": "https://app.example/api/v1/connections/oauth/google/callback",
        "scopes": ["read"],
    }
    settings = OAuthSettings(context="hosted", registrations=SecretStr(json.dumps({"hosted": value})))
    with pytest.raises(OAuthError, match="disabled"):
        settings.registration("hosted")
    enabled = settings.model_copy(update={"hosted_enabled": True})
    assert enabled.registration("hosted").owner == "langflow"
    assert "registration-secret" not in repr(enabled)
    assert "registration-secret" not in enabled.model_dump_json()
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps(value))
    assert safe_getenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS") is None
    redacted = _build_redact_processor(frozenset())(
        None,
        "info",
        {
            "client_secret": "registration-secret",  # pragma: allowlist secret - test fixture
            "private_key": "private-key",  # pragma: allowlist secret - deliberately invalid test fixture
            "code_verifier": "verifier",
            "client_assertion": "signed-assertion",
            "registrations": value,
        },
    )
    assert set(redacted.values()) == {"***"}


@pytest.mark.parametrize("provider", ["google", "microsoft", "slack"])
def test_public_clients_use_s256_and_no_client_secret(provider):
    registration = config(
        provider=provider,
        tenant="12345678-1234-1234-1234-123456789abc" if provider == "microsoft" else None,
        redirect_uri=f"http://localhost/api/v1/connections/oauth/{provider}/callback",
    )
    url = providers.authorization_url(registration, state="test-state", verifier="v" * 64, scopes=["read"])
    params = parse_qs(urlsplit(url).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"] == [providers.challenge("v" * 64)]
    assert "client_secret" not in providers.client_auth(registration)
    assert params["user_scope" if provider == "slack" else "scope"] == ["read"]


@pytest.mark.parametrize("profile", ["user", "bot"])
async def test_slack_token_selection_and_refresh_rotation(monkeypatch, profile):
    registration = config(
        provider="slack",
        profile=profile,
        client_type="confidential",
        client_secret="test-only",  # noqa: S106 - test fixture  # pragma: allowlist secret - deliberately invalid test fixture
        context="self_managed",
        allowed_tenants=["T1"],
        redirect_uri="https://app.example/api/v1/connections/oauth/slack/callback",
    )

    async def request(_url, data, **_kwargs):
        if data.get("grant_type") == "refresh_token":
            return {
                "ok": True,
                "access_token": "rotated",
                "refresh_token": "new-refresh",
                "expires_in": 43200,
                "scope": "read",
                "token_type": profile,
            }
        return {
            "ok": True,
            "access_token": "bot-access",
            "refresh_token": "bot-refresh",
            "token_type": "bot",
            "scope": "bot:read",
            "team": {"id": "T1", "name": "Test"},
            "bot_user_id": "B1",
            "authed_user": {
                "access_token": "user-access",
                "refresh_token": "user-refresh",
                "id": "U1",
                "token_type": "user",
                "scope": "user:read",
            },
        }

    monkeypatch.setattr(providers, "_request", request)
    payload, scopes, account = await providers.exchange(registration, code="test-code", previous_scopes=["read"])
    assert payload["access_token"] == f"{profile}-access"
    assert scopes == [f"{profile}:read"]
    assert account["tenant_id"] == "T1"
    refreshed, _, _ = await providers.exchange(
        registration, refresh_token=payload["refresh_token"], previous_scopes=scopes
    )
    assert refreshed["refresh_token"] == "new-refresh"  # noqa: S105 - test fixture
    assert refreshed["expires_at"] is not None


async def test_http_error_and_redirect_never_echo_provider_credentials(monkeypatch):
    original_client = httpx.AsyncClient
    for status in [302, 400, 500]:
        transport = httpx.MockTransport(
            lambda _request, status=status: httpx.Response(
                status, json={"error": "secret-code-refresh-token"}, headers={"Location": "https://elsewhere.example"}
            )
        )
        monkeypatch.setattr(
            providers.httpx,
            "AsyncClient",
            lambda transport=transport, **kwargs: original_client(transport=transport, **kwargs),
        )
        with pytest.raises(OAuthError) as error:
            await providers._request("https://oauth2.googleapis.com/token", {"code": "secret-code"})
        assert "secret-code" not in str(error.value)
        assert "refresh-token" not in str(error.value)


async def test_google_revoke_accepts_empty_success_response(monkeypatch):
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=b""))
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda transport=transport, **kwargs: original_client(transport=transport, **kwargs),
    )
    assert await providers.revoke(config(), {"access_token": "test-only-access"}) is True


def test_microsoft_certificate_assertion_is_short_lived_and_audience_bound():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    registration = config(
        provider="microsoft",
        client_type="confidential",
        context="self_managed",
        tenant="12345678-1234-1234-1234-123456789abc",
        private_key=private_key,
        certificate_thumbprint="aa" * 32,
        redirect_uri="https://app.example/api/v1/connections/oauth/microsoft/callback",
    )
    auth = providers.client_auth(registration)
    assertion = auth["client_assertion"]
    claims = jwt.decode(
        assertion, key.public_key(), algorithms=["PS256"], audience=providers.endpoints(registration)[1]
    )
    assert claims["iss"] == registration.client_id
    assert claims["sub"] == registration.client_id
    assert claims["exp"] - claims["nbf"] == 300
    assert jwt.get_unverified_header(assertion)["x5t#S256"]
    assert "client_secret" not in auth


async def test_google_tenant_restriction_rejects_unsigned_claims():
    registration = config(allowed_tenants=["example.com"], scopes=["openid", "email"])
    forged = jwt.encode({"hd": "example.com", "sub": "attacker"}, key="", algorithm="none")
    with pytest.raises(OAuthError, match="tenant"):
        await providers._google_account(registration, forged)


@pytest.mark.parametrize(("domain", "accepted"), [("example.com", True), ("other.example", False)])
async def test_google_restriction_verifies_signed_tenant_and_audience(monkeypatch, domain, accepted):
    import time

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public_jwk["kid"] = "test-key"
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"keys": [public_jwk]}))
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs))
    registration = config(allowed_tenants=["example.com"], scopes=["openid", "email"])
    claims = {
        "hd": domain,
        "sub": "test-user",
        "aud": registration.client_id,
        "iss": "https://accounts.google.com",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    if accepted:
        assert (await providers._google_account(registration, token))["tenant_id"] == domain
    else:
        with pytest.raises(OAuthError, match="tenant"):
            await providers._google_account(registration, token)
    wrong_audience = jwt.encode(
        {**claims, "aud": "different-client"}, key, algorithm="RS256", headers={"kid": "test-key"}
    )
    with pytest.raises(OAuthError, match="tenant"):
        await providers._google_account(registration, wrong_audience)
