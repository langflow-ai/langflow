"""Unit tests for streaming support: StreamChunk model and client.stream() / client.run()."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from langflow_sdk import AsyncClient, Client, StreamChunk
from langflow_sdk.exceptions import LangflowAuthError, LangflowConnectionError, LangflowHTTPError
from langflow_sdk.models import RunResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_URL = "http://langflow.test"
_FLOW_ID = "00000000-0000-0000-0000-000000000001"
_RUN_ENDPOINT = f"/api/v1/run/{_FLOW_ID}"


def _sse_body(*events: dict[str, Any]) -> bytes:
    """Encode a sequence of event dicts as newline-delimited JSON (backend SSE format)."""
    return b"\n\n".join(json.dumps(e).encode() for e in events) + b"\n\n"


class _MockTransport(httpx.BaseTransport):
    def __init__(
        self,
        *,
        status: int = 200,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._status = status
        self._content = content
        self._headers = headers or {"content-type": "text/event-stream"}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            self._status,
            content=self._content,
            headers=self._headers,
            request=request,
        )


class _AsyncMockTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        *,
        status: int = 200,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._status = status
        self._content = content
        self._headers = headers or {"content-type": "text/event-stream"}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            self._status,
            content=self._content,
            headers=self._headers,
            request=request,
        )


def _sync_client(transport: _MockTransport) -> Client:
    http = httpx.Client(base_url=_BASE_URL, transport=transport)
    return Client(_BASE_URL, httpx_client=http)


def _async_client(transport: _AsyncMockTransport) -> AsyncClient:
    http = httpx.AsyncClient(base_url=_BASE_URL, transport=transport)
    return AsyncClient(_BASE_URL, httpx_client=http)


# ---------------------------------------------------------------------------
# StreamChunk model tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_stream_chunk_token_text() -> None:
    chunk = StreamChunk(event="token", data={"chunk": "Hello"})
    assert chunk.text == "Hello"
    assert chunk.is_token is True
    assert chunk.is_end is False
    assert chunk.is_error is False


@pytest.mark.unit
def test_stream_chunk_token_no_chunk_key() -> None:
    chunk = StreamChunk(event="token", data={})
    assert chunk.text is None


@pytest.mark.unit
def test_stream_chunk_add_message_text() -> None:
    chunk = StreamChunk(event="add_message", data={"message": {"text": "Final answer", "sender": "AI"}})
    assert chunk.text == "Final answer"
    assert chunk.is_token is False


@pytest.mark.unit
def test_stream_chunk_add_message_no_text() -> None:
    chunk = StreamChunk(event="add_message", data={"message": {"sender": "AI"}})
    assert chunk.text is None


@pytest.mark.unit
def test_stream_chunk_add_message_non_dict_message() -> None:
    chunk = StreamChunk(event="add_message", data={"message": "raw string"})
    assert chunk.text is None


@pytest.mark.unit
def test_stream_chunk_end_event() -> None:
    chunk = StreamChunk(event="end", data={})
    assert chunk.is_end is True
    assert chunk.is_token is False
    assert chunk.is_error is False
    assert chunk.text is None


@pytest.mark.unit
def test_stream_chunk_error_event() -> None:
    chunk = StreamChunk(event="error", data={"error": "Something went wrong"})
    assert chunk.is_error is True
    assert chunk.is_end is False
    assert chunk.is_token is False


@pytest.mark.unit
def test_stream_chunk_other_event_text_is_none() -> None:
    chunk = StreamChunk(event="end_vertex", data={"vertex_id": "abc"})
    assert chunk.text is None
    assert chunk.is_token is False
    assert chunk.is_end is False
    assert chunk.is_error is False


@pytest.mark.unit
def test_stream_chunk_final_response_on_end() -> None:
    result_payload = {
        "session_id": "sess-1",
        "outputs": [],
    }
    chunk = StreamChunk(event="end", data={"result": result_payload})
    resp = chunk.final_response()
    assert resp is not None
    assert isinstance(resp, RunResponse)
    assert resp.session_id == "sess-1"


@pytest.mark.unit
def test_stream_chunk_final_response_no_result() -> None:
    chunk = StreamChunk(event="end", data={})
    assert chunk.final_response() is None


@pytest.mark.unit
def test_stream_chunk_final_response_non_end_event() -> None:
    chunk = StreamChunk(event="token", data={"chunk": "hi"})
    assert chunk.final_response() is None


@pytest.mark.unit
def test_stream_chunk_empty_data_defaults() -> None:
    chunk = StreamChunk(event="token")
    assert chunk.data == {}
    assert chunk.text is None


# ---------------------------------------------------------------------------
# LangflowClient.stream() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_stream_yields_token_chunks() -> None:
    events = [
        {"event": "token", "data": {"chunk": "Hello"}},
        {"event": "token", "data": {"chunk": " World"}},
        {"event": "end", "data": {"result": {"outputs": []}}},
    ]
    client = _sync_client(_MockTransport(content=_sse_body(*events)))
    chunks = list(client.stream(_FLOW_ID, input_value="hi"))
    assert len(chunks) == len(events)
    assert chunks[0].event == "token"
    assert chunks[0].text == "Hello"
    assert chunks[1].text == " World"
    assert chunks[2].is_end is True
    client.close()


@pytest.mark.unit
def test_sync_stream_skips_blank_lines() -> None:
    # Insert extra blank lines between events (normal in SSE format)
    body = b"\n\n" + json.dumps({"event": "token", "data": {"chunk": "A"}}).encode() + b"\n\n\n\n"
    client = _sync_client(_MockTransport(content=body))
    chunks = list(client.stream(_FLOW_ID, input_value="test"))
    assert len(chunks) == 1
    assert chunks[0].text == "A"
    client.close()


@pytest.mark.unit
def test_sync_stream_skips_invalid_json() -> None:
    body = b"not-json\n\n" + json.dumps({"event": "end", "data": {}}).encode() + b"\n\n"
    client = _sync_client(_MockTransport(content=body))
    chunks = list(client.stream(_FLOW_ID, input_value="test"))
    # Bad JSON line is skipped; only the end event comes through
    assert len(chunks) == 1
    assert chunks[0].is_end is True
    client.close()


@pytest.mark.unit
def test_sync_stream_skips_json_without_event_key() -> None:
    body = json.dumps({"no_event": "oops"}).encode() + b"\n\n"
    client = _sync_client(_MockTransport(content=body))
    chunks = list(client.stream(_FLOW_ID, input_value="test"))
    assert chunks == []
    client.close()


@pytest.mark.unit
def test_sync_stream_sets_stream_true_in_payload() -> None:
    """Verify the outgoing request payload always has stream=True."""
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, content=b"", headers={"content-type": "text/event-stream"}, request=request)

    http = httpx.Client(base_url=_BASE_URL, transport=_CapturingTransport())
    client = Client(_BASE_URL, httpx_client=http)
    list(client.stream(_FLOW_ID, input_value="hello"))
    client.close()

    assert len(captured) == 1
    payload = json.loads(captured[0].content)
    assert payload["stream"] is True
    assert payload["input_value"] == "hello"


@pytest.mark.unit
def test_sync_stream_raises_auth_error_on_401() -> None:
    body = json.dumps({"detail": "Unauthorized"}).encode()
    client = _sync_client(_MockTransport(status=401, content=body, headers={"content-type": "application/json"}))
    with pytest.raises(LangflowAuthError):
        list(client.stream(_FLOW_ID, input_value="hi"))
    client.close()


@pytest.mark.unit
def test_sync_stream_raises_http_error_on_500() -> None:
    body = json.dumps({"detail": "Internal server error"}).encode()
    client = _sync_client(_MockTransport(status=500, content=body, headers={"content-type": "application/json"}))
    with pytest.raises(LangflowHTTPError):
        list(client.stream(_FLOW_ID, input_value="hi"))
    client.close()


@pytest.mark.unit
def test_sync_stream_raises_connection_error() -> None:
    class _ErrorTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
            msg = "refused"
            raise httpx.ConnectError(msg)

    http = httpx.Client(base_url=_BASE_URL, transport=_ErrorTransport())
    client = Client(_BASE_URL, httpx_client=http)
    with pytest.raises(LangflowConnectionError):
        list(client.stream(_FLOW_ID, input_value="hi"))
    client.close()


@pytest.mark.unit
def test_sync_stream_passes_tweaks() -> None:
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, content=b"", headers={"content-type": "text/event-stream"}, request=request)

    http = httpx.Client(base_url=_BASE_URL, transport=_CapturingTransport())
    client = Client(_BASE_URL, httpx_client=http)
    list(client.stream(_FLOW_ID, tweaks={"MyComponent": {"key": "val"}}))
    client.close()

    payload = json.loads(captured[0].content)
    assert payload["tweaks"] == {"MyComponent": {"key": "val"}}


# ---------------------------------------------------------------------------
# LangflowClient.run() convenience tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_run_returns_run_response() -> None:
    body = json.dumps({"session_id": "s1", "outputs": []}).encode()
    client = _sync_client(_MockTransport(content=body, headers={"content-type": "application/json"}))
    result = client.run(_FLOW_ID, input_value="Hello")
    assert isinstance(result, RunResponse)
    assert result.session_id == "s1"
    client.close()


@pytest.mark.unit
def test_sync_run_sends_correct_payload() -> None:
    captured: list[httpx.Request] = []

    class _CapturingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                content=json.dumps({"session_id": None, "outputs": []}).encode(),
                headers={"content-type": "application/json"},
                request=request,
            )

    http = httpx.Client(base_url=_BASE_URL, transport=_CapturingTransport())
    client = Client(_BASE_URL, httpx_client=http)
    client.run(_FLOW_ID, input_value="test", input_type="text", output_type="text")
    client.close()

    payload = json.loads(captured[0].content)
    assert payload["input_value"] == "test"
    assert payload["input_type"] == "text"
    assert payload["output_type"] == "text"
    # run() must NOT set stream=True
    assert payload.get("stream", False) is False


# ---------------------------------------------------------------------------
# AsyncLangflowClient.stream() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_stream_yields_token_chunks() -> None:
    events = [
        {"event": "token", "data": {"chunk": "Async"}},
        {"event": "end", "data": {"result": {"outputs": []}}},
    ]
    client = _async_client(_AsyncMockTransport(content=_sse_body(*events)))
    chunks = [c async for c in client.stream(_FLOW_ID, input_value="hi")]
    assert len(chunks) == len(events)
    assert chunks[0].event == "token"
    assert chunks[0].text == "Async"
    assert chunks[1].is_end is True
    await client.aclose()


@pytest.mark.unit
async def test_async_stream_skips_blank_lines() -> None:
    body = b"\n\n" + json.dumps({"event": "token", "data": {"chunk": "X"}}).encode() + b"\n\n"
    client = _async_client(_AsyncMockTransport(content=body))
    chunks = [c async for c in client.stream(_FLOW_ID, input_value="test")]
    assert len(chunks) == 1
    assert chunks[0].text == "X"
    await client.aclose()


@pytest.mark.unit
async def test_async_stream_raises_auth_error_on_401() -> None:
    body = json.dumps({"detail": "Unauthorized"}).encode()
    client = _async_client(_AsyncMockTransport(status=401, content=body, headers={"content-type": "application/json"}))
    with pytest.raises(LangflowAuthError):
        async for _ in client.stream(_FLOW_ID, input_value="hi"):
            pass
    await client.aclose()


@pytest.mark.unit
async def test_async_stream_raises_connection_error() -> None:
    class _AsyncErrorTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
            msg = "refused"
            raise httpx.ConnectError(msg)

    http = httpx.AsyncClient(base_url=_BASE_URL, transport=_AsyncErrorTransport())
    client = AsyncClient(_BASE_URL, httpx_client=http)
    with pytest.raises(LangflowConnectionError):
        async for _ in client.stream(_FLOW_ID, input_value="hi"):
            pass
    await client.aclose()


@pytest.mark.unit
async def test_async_stream_sets_stream_true_in_payload() -> None:
    captured: list[httpx.Request] = []

    class _AsyncCapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, content=b"", headers={"content-type": "text/event-stream"}, request=request)

    http = httpx.AsyncClient(base_url=_BASE_URL, transport=_AsyncCapturingTransport())
    client = AsyncClient(_BASE_URL, httpx_client=http)
    async for _ in client.stream(_FLOW_ID, input_value="hello"):
        pass
    await client.aclose()

    payload = json.loads(captured[0].content)
    assert payload["stream"] is True
    assert payload["input_value"] == "hello"


# ---------------------------------------------------------------------------
# AsyncLangflowClient.run() convenience tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_run_returns_run_response() -> None:
    body = json.dumps({"session_id": "async-s1", "outputs": []}).encode()
    client = _async_client(_AsyncMockTransport(content=body, headers={"content-type": "application/json"}))
    result = await client.run(_FLOW_ID, input_value="Hello")
    assert isinstance(result, RunResponse)
    assert result.session_id == "async-s1"
    await client.aclose()


@pytest.mark.unit
async def test_async_run_does_not_set_stream_true() -> None:
    captured: list[httpx.Request] = []

    class _AsyncCapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                content=json.dumps({"session_id": None, "outputs": []}).encode(),
                headers={"content-type": "application/json"},
                request=request,
            )

    http = httpx.AsyncClient(base_url=_BASE_URL, transport=_AsyncCapturingTransport())
    client = AsyncClient(_BASE_URL, httpx_client=http)
    await client.run(_FLOW_ID, input_value="async test")
    await client.aclose()

    payload = json.loads(captured[0].content)
    assert payload.get("stream", False) is False


# ---------------------------------------------------------------------------
# Public export check
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_stream_chunk_importable_from_package() -> None:
    import langflow_sdk

    assert langflow_sdk.StreamChunk is StreamChunk
