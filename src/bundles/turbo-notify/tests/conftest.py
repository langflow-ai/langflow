"""Shared fixtures: every request the components make goes to an in-memory transport."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from lfx_turbo_notify import _client

API_KEY = "tn_test_0000000000000000"  # pragma: allowlist secret
MESSAGE_ID = "msg_" + "0123456789abcdef" * 2
OTHER_MESSAGE_ID = "msg_" + "fedcba9876543210" * 2
CONTACT_ID = "ct_" + "a1b2c3d4e5f60718" * 2
GROUP_ID = "grp_" + "9f6f0b37c98043e5" * 2
PHONE = "+12025550123"


@dataclass
class Network:
    """Records the requests and answers them with the queued responses."""

    requests: list[httpx.Request] = field(default_factory=list)
    responses: list[httpx.Response | Exception] = field(default_factory=list)

    def queue(self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None, **kwargs) -> None:
        if body is None:
            self.responses.append(httpx.Response(status, headers=headers, **kwargs))
        else:
            self.responses.append(httpx.Response(status, json=body, headers=headers, **kwargs))

    def queue_error(self, error: Exception) -> None:
        self.responses.append(error)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    @property
    def last_json(self) -> Any:
        return json.loads(self.last.content)


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> Network:
    """Replace the HTTP client factory so no test ever opens a real connection."""
    net = Network()

    def make_client(timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(net.handle), timeout=timeout)

    monkeypatch.setattr(_client, "make_http_client", make_client)
    return net


def build(component_class, **inputs):
    """Create a component with the API key set, plus any inputs."""
    return component_class(api_key=API_KEY, **inputs)
