"""Expected WhatsApp setup failures retain guidance without echoing provider data."""

from types import SimpleNamespace

import pytest
from langflow.services.connection import service
from langflow.services.connection.slack_credentials import ManualCredentialError
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.whatsapp.credentials import validate_manual_credential
from lfx.integrations.errors import ConnectionNotAuthorizedError

from .support import operator

__all__ = ["operator"]
pytestmark = [pytest.mark.no_blockbuster, pytest.mark.usefixtures("operator")]


@pytest.mark.parametrize(
    "hint",
    [
        "Use this app's system-user token with both WhatsApp permissions.",
        "The configured phone must belong to the configured WABA.",
    ],
)
async def test_expected_whatsapp_validation_hint_reaches_connection_response(monkeypatch, hint):
    async def reject(_self):
        raise ConnectionNotAuthorizedError(provider="whatsapp", hint=hint)

    monkeypatch.setattr("lfx_whatsapp._client.WhatsAppClient.verify_account", reject)
    monkeypatch.setattr(service, "deployment_context", lambda: "self_managed")
    monkeypatch.setattr(
        registry,
        "get_provider",
        lambda _provider: SimpleNamespace(
            validate_manual_credential=validate_manual_credential, manual_token_requires_expiry=False
        ),
    )
    payload = ConnectionCreate.model_validate(
        {
            "provider_key": "whatsapp",
            "name": "business",
            "display_name": "Business",
            "executing_identity": {"identity": "service"},
            "credentials": {"access_token": "synthetic-private-token"},
        }
    )
    with pytest.raises(ManualCredentialError) as caught:
        await service._validate_manual_credentials(payload)
    assert str(caught.value) == hint
    assert "synthetic-private-token" not in str(caught.value)


async def test_unsupported_whatsapp_context_explains_server_requirement():
    payload = ConnectionCreate.model_validate(
        {
            "provider_key": "whatsapp",
            "name": "business",
            "display_name": "Business",
            "executing_identity": {"identity": "service"},
            "credentials": {"access_token": "synthetic-private-token"},
        }
    )
    with pytest.raises(ManualCredentialError, match="hosted or self-managed server"):
        await validate_manual_credential(payload, context="desktop")
