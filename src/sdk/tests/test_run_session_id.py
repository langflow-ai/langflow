"""V1 run requests preserve caller-selected conversation IDs on the wire."""

from __future__ import annotations

import json

import httpx
import pytest
from langflow_sdk import AsyncClient, Client
from langflow_sdk.models import RunRequest

_BASE_URL = "http://langflow.test"
_FLOW_ID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.unit
@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize(
    "session_ids",
    [None, ["conversation-a", "conversation-b", "conversation-a"], [""]],
    ids=["omitted", "separate-and-resumed-conversations", "empty"],
)
async def test_run_flow_session_ids(*, async_mode: bool, session_ids: list[str] | None) -> None:
    captured: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"/api/v1/run/{_FLOW_ID}"
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"session_id": "server-result", "outputs": []})

    requests = (
        [RunRequest(input_value="Hello")]
        if session_ids is None
        else [RunRequest(input_value="Hello", session_id=session_id) for session_id in session_ids]
    )
    transport = httpx.MockTransport(handle)
    if async_mode:
        async with httpx.AsyncClient(base_url=_BASE_URL, transport=transport) as http:
            client = AsyncClient(_BASE_URL, httpx_client=http)
            for request in requests:
                response = await client.run_flow(_FLOW_ID, request)
                assert response.session_id == "server-result"
    else:
        with httpx.Client(base_url=_BASE_URL, transport=transport) as http:
            client = Client(_BASE_URL, httpx_client=http)
            for request in requests:
                response = client.run_flow(_FLOW_ID, request)
                assert response.session_id == "server-result"

    assert len(captured) == len(requests)
    for body in captured:
        assert body["input_value"] == "Hello"
    if session_ids is None:
        assert "session_id" not in captured[0]
    else:
        assert [body.get("session_id") for body in captured] == session_ids
