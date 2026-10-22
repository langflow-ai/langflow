"""Telegram Bot API contracts use synthetic HTTP responses and real leases."""

from __future__ import annotations

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

TOKEN = "123456789:" + "a" * 35
BOT = {"id": 123456789, "is_bot": True, "username": "example_bot"}


class Resolver:
    def __init__(self, tokens=None, identity="bot", account_id="123456789"):
        self.tokens = tokens or [TOKEN]
        self.identity = identity
        self.account_id = account_id
        self.calls = []

    async def resolve(self, request):
        self.calls.append(request)
        token = self.tokens[min(len(self.calls) - 1, len(self.tokens) - 1)]
        return ResolvedCredential(
            access_token=SecretStr(token),
            provider="telegram",
            identity=self.identity,
            account=ConnectionAccount(id=self.account_id) if self.account_id else None,
            owner_kind="user",
        )


def lease(resolver=None):
    return CredentialLease(
        resolver or Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="telegram", name="bot"),
            principal=ExecutionPrincipal(kind="actor", user_id="test-user", interactive=True),
        ),
    )


class BotTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def handler(self, request):
        import json

        self.calls.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            return httpx.Response(response[0], json=response[1])
        return httpx.Response(200, json={"ok": True, "result": response})

    def install(self, monkeypatch):
        def factory():
            return httpx.MockTransport(self.handler)

        monkeypatch.setattr("lfx_telegram._client.httpx.AsyncHTTPTransport", lambda **_kwargs: factory())
        return self


def component(cls, **kwargs):
    value = cls(connection="telegram/bot", **kwargs)
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
