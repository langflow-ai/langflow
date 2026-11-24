"""Error events raised mid-stream on ``POST /api/v1/responses``."""

import json

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import endpoints

CHAT_FLOW_DATA = {
    "nodes": [
        {"id": "ChatInput-1", "data": {"type": "ChatInput"}},
        {"id": "ChatOutput-1", "data": {"type": "ChatOutput"}},
    ],
    "edges": [],
}


def _sse_payloads(body: str) -> list[str]:
    return [line.removeprefix("data: ") for line in body.splitlines() if line.startswith("data: ")]


async def test_stream_error_is_sent_as_openai_error_chunk(
    client: AsyncClient,
    logged_in_headers: dict,
    created_api_key,
    monkeypatch: pytest.MonkeyPatch,
):
    """A run failure reaches the client as a failed content chunk, not a custom ``event: error`` frame."""
    flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "responses-stream-error", "data": CHAT_FLOW_DATA},
        headers=logged_in_headers,
    )
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text

    async def failing_run(**_kwargs):
        msg = "Simulated streaming error"
        raise RuntimeError(msg)

    # Only graph execution is faked: the real run_flow_generator still turns the
    # failure into an ``error`` event that the responses stream must translate.
    monkeypatch.setattr(endpoints, "simple_run_flow", failing_run)

    response = await client.post(
        "api/v1/responses",
        json={"model": flow_resp.json()["id"], "input": "hello", "stream": True},
        headers={"x-api-key": created_api_key.api_key},
    )

    assert response.status_code == status.HTTP_200_OK
    assert "event: error" not in response.text
    payloads = _sse_payloads(response.text)
    assert payloads[-1] == "[DONE]"
    error_chunk = json.loads(payloads[-2])
    assert error_chunk.get("status") == "failed", error_chunk
    assert error_chunk.get("finish_reason") == "error", error_chunk
    # The API key's user owns the flow, so the underlying message is not redacted.
    assert error_chunk["delta"] == {"content": "Simulated streaming error"}
