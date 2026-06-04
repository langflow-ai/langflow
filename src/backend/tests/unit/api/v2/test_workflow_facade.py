"""Contract tests for the v2 workflow endpoints on the BackgroundExecutionService.

Phase 2 already routed the background POST / events / stop branches through the
facade. These tests close the Phase 3 endpoint-layer gaps and pin the wire
contract so the cutover stays backward compatible:

* ``links.events`` is part of the ``WorkflowJobResponse`` shape (additive).
* an optional ``idempotency_key`` dedupes background submits (returns the same
  job_id rather than queuing duplicate work).
* a re-enqueued QUEUED job (restart-surviving) replays its ORIGINAL inputs,
  because the submit request is persisted on the job row.
* ``GET`` status surfaces the durable ``Job.error`` additively without changing
  the top-level ``WorkflowJobResponse`` / ``WorkflowExecutionResponse`` shape.

Real client + real flows, no mocking of our own code.
"""

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope


def _body(flow_id, *, message: str = "hello", mode: str = "background", protocol: str = "langflow") -> dict:
    return {
        "flow_id": str(flow_id),
        "input_value": message,
        "mode": mode,
        "stream_protocol": protocol,
        "session_id": "thread-1",
    }


@pytest.fixture
async def chatbot_flow(created_api_key, json_memory_chatbot_no_llm):
    """Create a real no-LLM chatbot flow owned by the API-key user."""
    raw = json.loads(json_memory_chatbot_no_llm)
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="Facade Chatbot Flow",
            description="No-LLM chatbot flow for facade endpoint tests",
            data=raw.get("data", raw),
            user_id=created_api_key.user_id,
        )
        session.add(flow)
        await session.flush()
    yield flow_id
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


class TestBackgroundSubmitContract:
    """mode=background returns the unchanged WorkflowJobResponse wire shape."""

    async def test_background_returns_job_response_shape(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """POST mode=background returns a WorkflowJobResponse with the same fields."""
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflows",
            json=_body(chatbot_flow, mode="background"),
            headers=headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["object"] == "job"
        assert result["flow_id"] == str(chatbot_flow)
        assert result["status"] == "queued"
        assert result.get("job_id")
        # Unchanged links: status + stop.
        assert result["links"]["status"] == f"/api/v2/workflows?job_id={result['job_id']}"
        assert result["links"]["stop"] == "/api/v2/workflows/stop"
        # New additive link: re-attach events URL must point at the job.
        assert result["links"]["events"] == f"/api/v2/workflows/{result['job_id']}/events"
