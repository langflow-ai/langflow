"""Contract test locking the synchronous semantics of ``POST /flows/{id}/run``.

``lfx serve``'s run endpoint executes the flow and returns the completed result
in the response body — it is NOT a job-submission endpoint that returns a task id
to poll. This contract underpins the per-request-isolation model (a request maps
to exactly one synchronous execution that finishes before the worker recycles),
so it is locked with an explicit test. Streaming clients use
``POST /flows/{id}/stream`` instead.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
from lfx.graph import Graph
from lfx.graph.schema import ResultData
from lfx.schema.message import Message

FLOW_ID = "00000000-0000-0000-0000-000000000001"
DATA_DIR = Path(__file__).parent.parent.parent / "data"


@pytest.fixture
def warmed_client(monkeypatch):
    """A TestClient over a single warmed flow with a real graph + mocked execution."""
    from lfx.services.deps import get_settings_service

    with (DATA_DIR / "simple_chat_no_llm.json").open() as f:
        simple_chat_json = json.load(f)

    graph = Graph.from_payload(simple_chat_json, flow_id=FLOW_ID)

    async def mock_async_start(inputs, **kwargs):  # noqa: ARG001
        result_data = ResultData(
            results={"message": Message(text="Hello from flow")},
            component_display_name="Chat Output",
            component_id=graph.vertices[-1].id if graph.vertices else "test-123",
        )
        mock_result = MagicMock()
        mock_result.vertex.custom_component.display_name = "Chat Output"
        mock_result.vertex.id = result_data.component_id
        mock_result.result_dict = result_data
        yield mock_result

    graph.async_start = mock_async_start

    registry = FlowRegistry()
    registry.add(graph, FlowMeta(id=FLOW_ID, relative_path="test.json", title="Test Flow", description=None))

    app = create_multi_serve_app(registry=registry)
    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)

    with patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}):  # pragma: allowlist secret
        yield TestClient(app)


def test_run_endpoint_returns_completed_result(warmed_client):
    headers = {"x-api-key": "test-api-key"}

    with (
        patch.dict(os.environ, {"LANGFLOW_API_KEY": "test-api-key"}),  # pragma: allowlist secret
        patch("lfx.cli.common.extract_structured_result") as mock_extract,
    ):
        mock_extract.return_value = {
            "result": "Hello from flow",
            "success": True,
            "type": "message",
            "component": "Chat Output",
        }
        resp = warmed_client.post(f"/flows/{FLOW_ID}/run", json={"input_value": "hi"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    # A completed result, not a job/task handle to poll.
    assert "result" in body
    assert "success" in body
    assert "task_id" not in body
    assert "job_id" not in body
