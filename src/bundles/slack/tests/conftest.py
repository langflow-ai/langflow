"""Recorded-fixture harness for the ``lfx-slack`` contract tests.

The tests exercise the real ``slack_sdk`` request assembly, the real
``AsyncSlackResponse`` construction and the real ``SlackApiError`` raising --
only the network hop is replaced. ``AsyncBaseClient._request`` is the lowest
layer of the SDK that returns a plain dict, so patching it there keeps
everything above it under test while never touching aiohttp.

Nothing here imports ``langflow``: the bundle is installed by
.github/workflows/cross-bundle-test.yml into a venv holding only ``lfx``, this
bundle, and pytest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from lfx.integrations.models import ConnectionAccount, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr
from slack_sdk.web.async_base_client import AsyncBaseClient

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Return a recorded Slack Web API response body."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@dataclass
class RecordedCall:
    """One captured Web API request."""

    http_verb: str
    api_url: str
    req_args: dict[str, Any]

    @property
    def method(self) -> str:
        return self.api_url.rsplit("/", 1)[-1]

    @property
    def params(self) -> dict[str, Any]:
        """The form-encoded body slack_sdk assembled for this call."""
        data = self.req_args.get("data") or {}
        params = self.req_args.get("params") or {}
        merged = dict(data)
        merged.update(params)
        json_body = self.req_args.get("json")
        if isinstance(json_body, dict):
            merged.update(json_body)
        return merged

    @property
    def authorization(self) -> str | None:
        return (self.req_args.get("headers") or {}).get("Authorization")


@dataclass
class SlackTransport:
    """Queue of recorded responses, in the order the component will ask for them."""

    responses: list[dict[str, Any]] = field(default_factory=list)
    calls: list[RecordedCall] = field(default_factory=list)

    def enqueue(
        self,
        body: dict[str, Any],
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> SlackTransport:
        self.responses.append({"data": body, "status_code": status_code, "headers": headers or {}})
        return self

    def install(self, monkeypatch: pytest.MonkeyPatch) -> SlackTransport:
        transport = self

        async def _request(_client: AsyncBaseClient, *, http_verb: str, api_url: str, req_args: dict) -> dict:
            transport.calls.append(RecordedCall(http_verb=http_verb, api_url=api_url, req_args=req_args))
            if not transport.responses:
                msg = f"No recorded Slack response left for {api_url}"
                raise AssertionError(msg)
            return transport.responses.pop(0)

        monkeypatch.setattr(AsyncBaseClient, "_request", _request)
        return self

    @property
    def last(self) -> RecordedCall:
        return self.calls[-1]


class FakeResolver:
    """Minimal ``ConnectionResolverProtocol`` returning a scripted credential."""

    def __init__(
        self,
        *,
        identity: str | None = "user_delegated",
        tokens: list[str] | None = None,
        owner_kind: str = "user",
    ) -> None:
        self._identity = identity
        self._tokens = list(tokens or ["xoxp-first-token"])  # pragma: allowlist secret
        self.owner_kind = owner_kind
        self.requests: list[Any] = []

    async def resolve(self, request: Any) -> ResolvedCredential:
        self.requests.append(request)
        token = self._tokens[min(len(self.requests) - 1, len(self._tokens) - 1)]
        return ResolvedCredential(
            access_token=SecretStr(token),
            provider="slack",
            name=request.ref.name,
            owner_kind=self.owner_kind,
            identity=self._identity,
            granted_scopes=frozenset(request.required_scopes),
            scopes_verified=True,
            account=ConnectionAccount(id="U0SLACKUSER", display="Acme", tenant_id="T0SLACKTEAM"),
        )

    async def describe(self, _ref: Any, _principal: Any) -> None:
        return None


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> SlackTransport:
    """A recorded Slack transport already patched over ``slack_sdk``."""
    return SlackTransport().install(monkeypatch)


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    """A user-identity connection resolver wired into ``lfx.services.deps``."""
    fake = FakeResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


def build_component(component_class: type, **kwargs: Any):
    """Instantiate a Slack component with an interactive graph principal."""
    component = component_class(connection="slack/workspace", **kwargs)
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
        flow_id="flow-1",
        run_id="run-1",
        session_id="session-1",
    )
    component.set_vertex(SimpleNamespace(graph=graph))
    return component
