"""INT-13: the docs sample flow resolves connections per request under ``lfx serve``.

These tests are the CI target for the reference documentation
(``docs/docs/Lfx/lfx-connections.mdx``): they drive the real serve app with the
sample component from ``docs/docs/Lfx/samples/connections`` so the documented
request shape, the request-scope precedence, and the missing-connection behavior
cannot drift from what the server actually does.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app

from tests.unit.services.connection.sample_loader import load_connection_sample

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

FLOW_ID = "00000000-0000-0000-0000-0000000013a1"
ENV_KEY = "LF_CONNECTION__GOOGLE__WORK"
API_KEY = "int13-test-api-key"  # pragma: allowlist secret


def _build_flow() -> Graph:
    module = load_connection_sample("connection_action_component")
    graph = module.build_graph()
    graph.flow_id = FLOW_ID
    return graph


@pytest.fixture
def serve_client(monkeypatch: pytest.MonkeyPatch):
    """Serve the sample flow with ``--no-env-fallback`` semantics."""
    from lfx.services.deps import get_settings_service

    registry = FlowRegistry(no_env_fallback=True)
    registry.add(
        _build_flow(),
        FlowMeta(id=FLOW_ID, relative_path="connection_action_component.py", title="Connection sample"),
    )
    app = create_multi_serve_app(registry=registry)
    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)
    with patch.dict(os.environ, {"LANGFLOW_API_KEY": API_KEY}):
        yield TestClient(app)


def _run(client: TestClient, **body) -> tuple[int, dict]:
    response = client.post(
        f"/flows/{FLOW_ID}/run",
        json={"input_value": "describe my connection", **body},
        headers={"x-api-key": API_KEY},
    )
    return response.status_code, response.json()


def test_run_with_request_scoped_connection_succeeds(serve_client: TestClient) -> None:
    credential = json.dumps(
        {
            "access_token": "request-scoped-token",  # pragma: allowlist secret
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
            "account": {"id": "person@example.com"},
        }
    )

    status, payload = _run(serve_client, global_vars={ENV_KEY: credential})

    assert status == 200, payload
    assert payload["success"] is True
    assert "account=person@example.com" in payload["result"]
    assert "scopes_verified=True" in payload["result"]
    assert "request-scoped-token" not in json.dumps(payload)


def test_run_without_connection_reports_the_sanitized_unresolved_error(serve_client: TestClient) -> None:
    """A missing connection surfaces at lease time, not as a pre-flight rejection.

    ``lfx serve`` has no connection pre-flight (that is ``lfx run --check-variables``),
    and the run route has no machine-readable error code: the failure arrives as a
    500 whose text is ``ConnectionUnresolvedError``'s sanitized message. The
    documentation states exactly this, so assert on the text.
    """
    status, payload = _run(serve_client)

    assert status == 500
    assert payload["success"] is False
    assert "google/work" in payload["result"]
    assert ENV_KEY in payload["result"]


def test_environment_credential_is_ignored_under_no_env_fallback(
    serve_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_KEY, "ambient-token-must-not-win")

    status, payload = _run(serve_client)

    assert status == 500
    assert ENV_KEY in payload["result"]
    assert "ambient-token-must-not-win" not in json.dumps(payload)


def test_request_scope_does_not_leak_into_the_next_request(serve_client: TestClient) -> None:
    first_status, _ = _run(serve_client, global_vars={ENV_KEY: "first-request-token"})
    assert first_status == 200

    second_status, payload = _run(serve_client)

    assert second_status == 500
    assert "first-request-token" not in json.dumps(payload)
