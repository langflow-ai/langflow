"""Wire-level V1 streaming negotiation, independent of response parsing fixtures."""

import json

import httpx
import pytest
from langflow_sdk import AsyncClient, Client

_BASE = "http://langflow.test"
_FLOW = "00000000-0000-0000-0000-000000000001"
_KEY = "local-test-key"


def _check_request(request: httpx.Request, *, streaming: bool) -> None:
    assert request.method == "POST"
    assert request.url.path == f"/api/v1/run/{_FLOW}"
    assert dict(request.url.params) == ({"stream": "true"} if streaming else {})
    assert request.headers["x-api-key"] == _KEY
    assert json.loads(request.content) == {
        "input_value": "hello",
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": {"ChatInput": {"sender_name": "Test"}},
        "stream": streaming,
    }


def _response(request: httpx.Request, *, streaming: bool) -> httpx.Response:
    _check_request(request, streaming=streaming)
    if streaming:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'{"event":"error","data":{"error":"local failure"}}\n\n',
        )
    return httpx.Response(200, json={"outputs": []})


@pytest.mark.parametrize("streaming", [False, True])
def test_sync_run_transport_contract(*, streaming: bool) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _response(request, streaming=streaming)

    with (
        httpx.Client(base_url=_BASE, headers={"x-api-key": _KEY}, transport=httpx.MockTransport(handle)) as http,
        Client(_BASE, httpx_client=http) as client,
    ):
        kwargs = {"input_value": "hello", "tweaks": {"ChatInput": {"sender_name": "Test"}}}
        if streaming:
            chunks = list(client.stream(_FLOW, **kwargs))
            assert len(chunks) == 1
            assert chunks[0].is_error
            assert chunks[0].data == {"error": "local failure"}
        else:
            assert client.run(_FLOW, **kwargs).outputs == []
    assert len(calls) == 1


@pytest.mark.parametrize("streaming", [False, True])
async def test_async_run_transport_contract(*, streaming: bool) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _response(request, streaming=streaming)

    async with (
        httpx.AsyncClient(base_url=_BASE, headers={"x-api-key": _KEY}, transport=httpx.MockTransport(handle)) as http,
        AsyncClient(_BASE, httpx_client=http) as client,
    ):
        kwargs = {"input_value": "hello", "tweaks": {"ChatInput": {"sender_name": "Test"}}}
        if streaming:
            chunks = [chunk async for chunk in client.stream(_FLOW, **kwargs)]
            assert len(chunks) == 1
            assert chunks[0].is_error
            assert chunks[0].data == {"error": "local failure"}
        else:
            assert (await client.run(_FLOW, **kwargs)).outputs == []
    assert len(calls) == 1
