"""Synthetic Discord HTTP contracts use real credential leases."""

import json
from types import SimpleNamespace

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

TOKEN = "synthetic-discord-bot-credential"  # noqa: S105  # pragma: allowlist secret - synthetic fixture
BOT = {"id": "123456789", "bot": True, "username": "example_bot"}
APP = {"id": "123456789", "flags": 1 << 19}
CHANNEL = {"id": "333", "guild_id": "222", "type": 0}
GATEWAY = {
    "url": "wss://gateway.discord.gg/",
    "shards": 1,
    "session_start_limit": {"remaining": 999, "reset_after": 60000, "max_concurrency": 1},
}


class Resolver:
    async def resolve(self, _request):
        return ResolvedCredential(
            access_token=SecretStr(TOKEN),
            provider="discord",
            identity="bot",
            owner_kind="user",
            account=ConnectionAccount(id=BOT["id"]),
        )


def lease():
    return CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="discord", name="bot"),
            principal=ExecutionPrincipal(kind="actor", user_id="test-user", interactive=True),
        ),
    )


class BotTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def handler(self, request):
        self.calls.append(
            (
                request.method,
                str(request.url),
                dict(request.headers),
                json.loads(request.content) if request.content else None,
            )
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            return httpx.Response(response[0], json=response[1])
        return httpx.Response(200, json=response)

    def install(self, monkeypatch):
        monkeypatch.setattr("lfx_discord._client._http_transport", lambda: httpx.MockTransport(self.handler))
        return self


def component(cls, **kwargs):
    value = cls(connection="discord/bot", **kwargs)
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="test-user", interactive=True),
        flow_id="test-flow",
        run_id="test-run",
    )
    value.set_attributes({"_graph": graph})
    return value


@pytest.fixture
def resolver(monkeypatch):
    value = Resolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: value)
    return value
