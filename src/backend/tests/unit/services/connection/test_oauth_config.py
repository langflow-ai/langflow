"""Actionable registration diagnostics must never echo operator configuration."""

import json

import pytest
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration, OAuthSettings

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


# --------------------------------------------------------------------------- #
# TRG-4: the Slack app-level signing secret
# --------------------------------------------------------------------------- #


def test_a_slack_registration_may_carry_a_signing_secret() -> None:
    """Slack signs events with an app secret that is not the OAuth client secret."""
    registration = OAuthRegistration.model_validate(
        {
            "provider": "slack",
            "profile": "bot",
            "client_id": "client",
            "client_secret": "shh",  # pragma: allowlist secret
            "signing_secret": "slack-signing-secret",  # pragma: allowlist secret
            "redirect_uri": "https://example.com/api/v1/connections/oauth/slack/callback",
            "scopes": ["chat:write"],
        }
    )
    assert registration.signing_secret.get_secret_value() == "slack-signing-secret"


def test_only_slack_registrations_carry_a_signing_secret(monkeypatch) -> None:
    """Microsoft and Google verify with a per-subscription secret Langflow mints.

    Checked through the operator-facing lookup rather than the model, because
    that is the path whose message an operator actually reads - and it must name
    the rule without echoing the secret that tripped it.
    """
    monkeypatch.setenv(
        "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS",
        json.dumps({"reg": registration(signing_secret=_PRIVATE_VALUE)}),
    )
    with pytest.raises(OAuthError) as error:
        OAuthSettings(context="self_managed").registration("reg")
    assert str(error.value) == "Only Slack registrations carry a signing secret"
    assert _PRIVATE_VALUE not in str(error.value)


def test_rotating_the_signing_secret_does_not_invalidate_existing_consent() -> None:
    """The fingerprint binds consent to scopes and client, not to rotatable secrets."""
    base = {
        "provider": "slack",
        "profile": "bot",
        "client_id": "client",
        "client_secret": "shh",  # pragma: allowlist secret
        "redirect_uri": "https://example.com/api/v1/connections/oauth/slack/callback",
        "scopes": ["chat:write"],
    }
    before = OAuthRegistration.model_validate({**base, "signing_secret": "old"})
    after = OAuthRegistration.model_validate({**base, "signing_secret": "new"})

    assert before.fingerprint() == after.fingerprint()
