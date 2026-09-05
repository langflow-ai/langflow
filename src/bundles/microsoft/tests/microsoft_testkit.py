"""Test kit for the lfx-microsoft bundle tests.

These tests run in the clean ``lfx`` + bundle virtualenv built by
``.github/workflows/cross-bundle-test.yml``: it holds pytest, pytest-asyncio,
lfx and this bundle, and nothing else. Keep every helper here dependent on
``lfx`` and ``httpx`` only -- no respx, no langflow.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from lfx.integrations.models import ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.base import BaseConnectionResolverService
from pydantic import SecretStr

FIXTURES = Path(__file__).parent / "fixtures" / "graph"


def graph_fixture(name: str) -> dict[str, Any]:
    """Load one recorded Microsoft Graph response body."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class RecordingResolver(BaseConnectionResolverService):
    """Resolver that hands out a canned credential and counts resolutions."""

    def __init__(self, credentials: list[ResolvedCredential]) -> None:
        super().__init__()
        self._credentials = credentials
        self.requests: list[Any] = []
        self.set_ready()

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def resolve(self, request):
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._credentials) - 1)
        return self._credentials[index]


def credential(
    token: str = "graph-token-1",  # noqa: S107 - a fake bearer value, not a credential
    *,
    scopes: frozenset[str] | set[str] | None = None,
    scopes_verified: bool = True,
    owner_kind: str = "user",
) -> ResolvedCredential:
    """Build a resolved credential for the delegated Microsoft profile."""
    return ResolvedCredential(
        access_token=SecretStr(token),
        granted_scopes=frozenset(scopes or set()),
        scopes_verified=scopes_verified,
        owner_kind=owner_kind,
        provider="microsoft",
        name="work",
    )


class TransportRecorder:
    """An ``httpx.MockTransport`` wrapper that records every request."""

    def __init__(self, handler) -> None:
        self.requests: list[httpx.Request] = []
        self._handler = handler
        self.transport = httpx.MockTransport(self._record)

    def _record(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    @property
    def first(self) -> httpx.Request:
        return self.requests[0]


def json_response(payload: Any, status_code: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    """Build a JSON Graph response."""
    return httpx.Response(status_code, json=payload, headers=headers)


def graph_error(code: str, status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    """Build a Graph error response body."""
    return httpx.Response(
        status_code,
        json={"error": {"code": code, "message": "recorded error"}},
        headers=headers,
    )


def stub_graph(principal: ExecutionPrincipal | None = None) -> SimpleNamespace:
    """Build the minimal graph surface ``resolve_connection`` reads.

    No route family stamps ``graph.execution_principal`` on the INT-5 stack
    tip, so tests stamp it explicitly. Canvas and ``/api/v1/run`` execution of
    these components needs INT-6 (LE-2464) for the same reason.
    """
    return SimpleNamespace(
        execution_principal=principal or ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
        flow_id=None,
        run_id=None,
    )


def build_component(
    component_class,
    recorder: TransportRecorder,
    *,
    principal: ExecutionPrincipal | None = None,
    **inputs: Any,
):
    """Instantiate a component with a stubbed graph and a mocked transport."""
    component = component_class(**inputs)
    # ``Component.graph`` is a read-only property backed by the vertex, so the
    # stub is attached the same way the runtime attaches it.
    component._vertex = SimpleNamespace(graph=stub_graph(principal))
    component.graph_transport = recorder.transport
    return component
