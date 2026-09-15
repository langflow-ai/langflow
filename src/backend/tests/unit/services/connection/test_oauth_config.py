"""Actionable registration diagnostics must never echo operator configuration."""

import json

import pytest
from langflow.services.connection.oauth.config import OAuthError, OAuthSettings

_PRIVATE_VALUE = "operator-value-must-not-leak"


def registration(**overrides):
    return {
        "provider": "google",
        "client_id": _PRIVATE_VALUE,
        "client_secret": _PRIVATE_VALUE,
        "redirect_uri": "https://app.example/api/v1/connections/oauth/google/callback",
        "scopes": ["read"],
        **overrides,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param('{"' + _PRIVATE_VALUE, "OAuth registrations must contain valid JSON.", id="malformed-json"),
        pytest.param("[]", "OAuth registrations must be a JSON object keyed by registration ID.", id="array"),
        pytest.param("null", "OAuth registrations must be a JSON object keyed by registration ID.", id="null"),
        pytest.param("42", "OAuth registrations must be a JSON object keyed by registration ID.", id="scalar"),
        pytest.param("{}", "OAuth registration ID is not configured.", id="unknown-registration"),
        pytest.param(
            json.dumps({_PRIVATE_VALUE: _PRIVATE_VALUE}),
            "OAuth registration must be a JSON object.",
            id="non-object-registration",
        ),
    ],
)
def test_registration_lookup_errors_are_specific_and_redacted(monkeypatch, raw, expected):
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", raw)
    with pytest.raises(OAuthError) as error:
        OAuthSettings(context="self_managed").registration(_PRIVATE_VALUE)
    assert str(error.value) == expected
    assert _PRIVATE_VALUE not in str(error.value)


@pytest.mark.parametrize(
    ("overrides", "missing", "expected"),
    [
        pytest.param({}, "client_id", "OAuth registration field 'client_id' is required.", id="missing-field"),
        pytest.param(
            {"redirect_uri": "https://app.example/" + _PRIVATE_VALUE},
            None,
            "OAuth redirect must be HTTPS (or loopback HTTP) at the provider callback",
            id="wrong-callback-path",
        ),
        pytest.param(
            {"redirect_uri": "https://[" + _PRIVATE_VALUE + "]/callback"},
            None,
            "OAuth redirect must be HTTPS (or loopback HTTP) at the provider callback",
            id="malformed-callback-host",
        ),
        pytest.param(
            {"private_key": _PRIVATE_VALUE},
            None,
            "Confidential clients require exactly one secret or private key",
            id="conflicting-credentials",
        ),
        pytest.param(
            {"client_type": "public"},
            None,
            "Public clients cannot contain registration secrets",
            id="public-client-secret",
        ),
        pytest.param(
            {"context": "hosted"},
            None,
            "OAuth registration is unavailable in this deployment context.",
            id="deployment-context",
        ),
        pytest.param(
            {"provider": _PRIVATE_VALUE},
            None,
            "OAuth registration field 'provider' is invalid.",
            id="invalid-literal",
        ),
        pytest.param(
            {"scopes": [{_PRIVATE_VALUE: _PRIVATE_VALUE}]},
            None,
            "OAuth registration field 'scopes' is invalid.",
            id="invalid-nested-value",
        ),
        pytest.param(
            {_PRIVATE_VALUE: _PRIVATE_VALUE},
            None,
            "OAuth registration contains unsupported fields.",
            id="unknown-field-name",
        ),
    ],
)
def test_registration_validation_errors_are_specific_and_redacted(monkeypatch, overrides, missing, expected):
    value = registration(**overrides)
    if missing:
        del value[missing]
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps({"work": value}))
    with pytest.raises(OAuthError) as error:
        OAuthSettings(context="self_managed").registration("work")
    assert str(error.value) == expected
    assert _PRIVATE_VALUE not in str(error.value)
