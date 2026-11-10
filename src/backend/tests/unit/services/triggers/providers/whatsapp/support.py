"""Synthetic Graph transport with real credential leases."""

import httpx
import pytest
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr

TOKEN = "synthetic-system-user-token"  # noqa: S105  # pragma: allowlist secret
DEBUG = {
    "data": {
        "is_valid": True,
        "type": "SYSTEM_USER",
        "app_id": "111",
        "expires_at": 0,
        "scopes": ["whatsapp_business_management", "whatsapp_business_messaging"],
    }
}
PHONES = {"data": [{"id": "333"}]}


@pytest.fixture(autouse=True)
def operator(monkeypatch):
    for key, value in {
        "APP_ID": "111",
        "WABA_ID": "222",
        "PHONE_ID": "333",
        "GRAPH_VERSION": "v25.0",
        "APP_SECRET": "a" * 32,
    }.items():
        monkeypatch.setenv("LANGFLOW_WHATSAPP_" + key, value)


class Resolver:
    async def resolve(self, _request):
        return ResolvedCredential(
            access_token=SecretStr(TOKEN),
            provider="whatsapp",
            identity="service",
            owner_kind="user",
            account=ConnectionAccount(id="333", tenant_id="111:222"),
            granted_scopes=frozenset({"whatsapp_business_management", "whatsapp_business_messaging"}),
            scopes_verified=True,
        )


def lease():
    return CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="whatsapp", name="business"),
            principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        ),
    )


class GraphTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def handler(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        status, body = response if isinstance(response, tuple) else (200, response)
        return httpx.Response(status, json=body)

    def install(self, monkeypatch):
        monkeypatch.setattr(
            "lfx_whatsapp._client.httpx.AsyncHTTPTransport", lambda **_kwargs: httpx.MockTransport(self.handler)
        )
        return self
