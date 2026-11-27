"""Project uploads must use the same multipart contract as the real API."""

from __future__ import annotations

import io
import zipfile
from email import policy
from email.parser import BytesParser

import httpx
import pytest
from langflow_sdk import AsyncClient, Client
from langflow_sdk.exceptions import (
    LangflowAuthError,
    LangflowConnectionError,
    LangflowHTTPError,
    LangflowValidationError,
)

_URL = "https://langflow.test"
_FLOW = {"id": "00000000-0000-0000-0000-000000000042", "name": "Imported flow"}


def _archive() -> bytes:
    """Build a small ZIP with binary data to catch encoding changes."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("flow.json", b'{"name":"Imported flow","data":null}')
        archive.writestr("binary.bin", bytes(range(256)))
    return stream.getvalue()


def _assert_upload(request: httpx.Request, content: bytes) -> None:
    """Inspect native HTTPX multipart bytes without depending on its encoder."""
    assert request.method == "POST"
    assert request.url == _URL + "/api/v1/projects/upload/"
    assert request.headers["x-api-key"] == "local-test-key"
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + request.headers["Content-Type"].encode() + b"\r\n\r\n" + request.content
    )
    assert message.is_multipart()
    parts = list(message.iter_parts())
    assert len(parts) == 1
    part = parts[0]
    assert part.get_param("name", header="Content-Disposition") == "file"
    assert part.get_filename() == "project.zip"
    assert part.get_content_type() == "application/zip"
    assert part.get_payload(decode=True) == content


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("injected", [False, True])
@pytest.mark.parametrize("content", [_archive(), b"", b"invalid zip\x00\xff"])
async def test_project_upload_multipart(asynchronous, injected, content: bytes, monkeypatch) -> None:
    """Send one intact file without altering defaults on either client kind."""
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        _assert_upload(request, content)
        return httpx.Response(201, json=[_FLOW])

    transport = httpx.MockTransport(handle)
    defaults = {"Content-Type": "application/json", "x-api-key": "local-test-key", "X-Custom": "preserved"}
    if asynchronous:
        native = httpx.AsyncClient(base_url=_URL, transport=transport, headers=defaults)
        if not injected:
            monkeypatch.setattr(httpx, "AsyncClient", lambda **_: native)
        client = AsyncClient(_URL, api_key="local-test-key", httpx_client=native if injected else None)
        original = dict(native.headers)
        try:
            flows = await client.upload_project(content)
            assert dict(native.headers) == original
            assert flows[0].name == _FLOW["name"]
        finally:
            await client.aclose()
            await native.aclose()
    else:
        native = httpx.Client(base_url=_URL, transport=transport, headers=defaults)
        if not injected:
            monkeypatch.setattr(httpx, "Client", lambda **_: native)
        client = Client(_URL, api_key="local-test-key", httpx_client=native if injected else None)
        original = dict(native.headers)
        try:
            flows = client.upload_project(content)
            assert dict(native.headers) == original
            assert flows[0].name == _FLOW["name"]
        finally:
            client.close()
            native.close()
    assert len(requests) == 1
    assert requests[0].headers["X-Custom"] == "preserved"


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, LangflowHTTPError),
        (401, LangflowAuthError),
        (403, LangflowAuthError),
        (422, LangflowValidationError),
        (500, LangflowHTTPError),
    ],
)
async def test_project_upload_http_errors(asynchronous, status: int, error: type[Exception]) -> None:
    """Keep the existing typed server-error mapping for upload failures."""

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "upload rejected"})

    transport = httpx.MockTransport(handle)
    if asynchronous:
        async with httpx.AsyncClient(base_url=_URL, transport=transport) as native:
            with pytest.raises(error, match="upload rejected"):
                await AsyncClient(_URL, httpx_client=native).upload_project(b"invalid")
    else:
        with (
            httpx.Client(base_url=_URL, transport=transport) as native,
            pytest.raises(error, match="upload rejected"),
        ):
            Client(_URL, httpx_client=native).upload_project(b"invalid")


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_project_upload_connection_error(asynchronous) -> None:
    """Retain connection error translation for both transports."""

    def handle(request: httpx.Request) -> httpx.Response:
        message = "offline"
        raise httpx.ConnectError(message, request=request)

    transport = httpx.MockTransport(handle)
    if asynchronous:
        async with httpx.AsyncClient(base_url=_URL, transport=transport) as native:
            with pytest.raises(LangflowConnectionError, match="Could not connect"):
                await AsyncClient(_URL, httpx_client=native).upload_project(b"invalid")
    else:
        with (
            httpx.Client(base_url=_URL, transport=transport) as native,
            pytest.raises(LangflowConnectionError, match="Could not connect"),
        ):
            Client(_URL, httpx_client=native).upload_project(b"invalid")
