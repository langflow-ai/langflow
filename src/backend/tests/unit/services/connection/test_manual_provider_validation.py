"""Provider token checks return safe errors before any credential is stored."""

from types import SimpleNamespace

import httpx
import pytest
from langflow.services.connection import service
from langflow.services.connection.slack_credentials import ManualCredentialError
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.triggers.providers import registry
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationError,
    IntegrationNetworkError,
    IntegrationPolicyBlockedError,
    InvalidRequestError,
    RateLimitedError,
    ScopeMissingError,
)
from lfx.utils.ssrf_protection import SSRFProtectionError

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(params=["gitlab", "whatsapp", "discord", "telegram"])
def token_payload(request):
    return ConnectionCreate.model_validate(
        {
            "provider_key": request.param,
            "name": "provider_check",
            "display_name": "Provider check",
            "executing_identity": {"identity": "service"},
            "credentials": {"access_token": "synthetic-provider-token"},  # pragma: allowlist secret
        }
    )


def install_validator(monkeypatch, validate):
    monkeypatch.setattr(service, "deployment_context", lambda: "self_managed")
    monkeypatch.setattr(
        registry,
        "get_provider",
        lambda _provider: SimpleNamespace(validate_manual_credential=validate, manual_token_requires_expiry=False),
    )


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (AuthExpiredError(), "Paste a valid token"),
        (ConnectionNotAuthorizedError(), "permissions and account access"),
        (ScopeMissingError(), "permissions and account access"),
        (RateLimitedError(), "Wait and try again"),
        (IntegrationNetworkError(reason="dns"), "outbound network and DNS"),
        (SSRFProtectionError("private provider detail"), "outbound network and DNS"),
        (httpx.ConnectError("private provider detail"), "outbound network and DNS"),
        (IntegrationError("private provider detail"), "could not check this token"),
        (InvalidRequestError("private provider detail"), "setup guide and token settings"),
        (ValueError("private provider detail"), "setup guide and token settings"),
    ],
)
async def test_provider_failures_become_safe_manual_errors(monkeypatch, token_payload, failure, message):
    async def validate(_payload, *, context):
        assert context == "self_managed"
        raise failure

    install_validator(monkeypatch, validate)
    with pytest.raises(ManualCredentialError, match=message) as caught:
        await service._validate_manual_credentials(token_payload)
    assert "private provider detail" not in str(caught.value)
    assert token_payload.credentials.access_token.get_secret_value() not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "error", [ManualCredentialError("Use the provider's supported bot token."), IntegrationPolicyBlockedError()]
)
async def test_provider_guidance_and_policy_denials_are_preserved(monkeypatch, token_payload, error):
    async def validate(_payload, *, context):  # noqa: ARG001
        raise error

    install_validator(monkeypatch, validate)
    with pytest.raises(type(error)) as caught:
        await service._validate_manual_credentials(token_payload)
    assert caught.value is error


async def test_validated_identity_is_returned(monkeypatch, token_payload):
    validated = token_payload.model_copy(update={"granted_scopes": ["verified"]})

    async def validate(payload, *, context):  # noqa: ARG001
        assert payload is token_payload
        return validated

    install_validator(monkeypatch, validate)
    assert await service._validate_manual_credentials(token_payload) is validated
