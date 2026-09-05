"""Shared harness for the connection-backed Google Workspace action tests.

The components never see a token: they ask ``resolve_connection`` for a lease and
the lease asks the host's connection resolver. In tests the resolver is a fake
that records what was asked for, and the Google client is driven by
``googleapiclient.http.HttpMockSequence`` against recorded response fixtures, so
the whole suite runs offline with no credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from googleapiclient.http import HttpMockSequence
from lfx.integrations.models import ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "google_workspace"

# Obviously fake. Every assertion about token leakage looks for this exact string.
FAKE_ACCESS_TOKEN = "fake-google-access-token-do-not-use"  # noqa: S105  # pragma: allowlist secret
FAKE_REFRESHED_TOKEN = "fake-google-refreshed-token"  # noqa: S105  # pragma: allowlist secret


def load_fixture(name: str) -> dict:
    """Return one recorded Google response body."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / f"{name}.json").read_bytes()


def json_response(name: str, status: str = "200") -> tuple[dict[str, str], bytes]:
    return ({"status": status, "content-type": "application/json"}, fixture_bytes(name))


def media_response(payload: bytes, status: str = "200") -> tuple[dict[str, str], bytes]:
    return ({"status": status, "content-type": "application/octet-stream"}, payload)


class FakeResolver:
    """Records every resolution request and hands back a canned credential."""

    def __init__(
        self,
        *,
        granted_scopes: frozenset[str] | None = None,
        owner_kind: str = "user",
        error: Exception | None = None,
    ) -> None:
        self.requests: list[Any] = []
        self.granted_scopes = granted_scopes
        self.owner_kind = owner_kind
        self.error = error

    async def resolve(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        token = FAKE_REFRESHED_TOKEN if request.rejected_token_digest else FAKE_ACCESS_TOKEN
        return ResolvedCredential(
            access_token=SecretStr(token),
            granted_scopes=self.granted_scopes if self.granted_scopes is not None else frozenset(),
            scopes_verified=self.granted_scopes is not None,
            connection_id="00000000-0000-0000-0000-000000000001",
            owner_kind=self.owner_kind,
            provider="google",
            name="work",
        )

    async def describe(self, _ref, _principal):
        return None


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    """Install a recording resolver in place of the host's."""
    fake = FakeResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


def wire(component, responses: list[tuple[dict[str, str], bytes]], *, connection: str = "google/work"):
    """Attach a graph principal, a connection handle and a canned HTTP sequence."""
    component.connection = connection
    component.set_vertex(
        SimpleNamespace(
            graph=SimpleNamespace(
                execution_principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
                flow_id="11111111-1111-1111-1111-111111111111",
                run_id="22222222-2222-2222-2222-222222222222",
            )
        )
    )
    http = HttpMockSequence(list(responses))
    component._workspace_http = http  # documented test seam, see _workspace_client._build_service
    return http
