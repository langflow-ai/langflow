"""Tests for ``parse_input_request_from_body``.

Regression coverage for the bug where multipart/form-data requests to
``/api/v1/run/{flow_id}`` silently dropped ``session_id``, ``input_value``,
and other form fields, routing conversations into the default session
(see GitHub issue #9859 and PR #10682).
"""

from __future__ import annotations

import io

import orjson
import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from langflow.api.v1.endpoints import parse_input_request_from_body
from langflow.api.v1.schemas import SimplifiedAPIRequest


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app that exposes the parser as an endpoint.

    Returning the parsed ``SimplifiedAPIRequest`` over the wire lets us drive
    real multipart/JSON request bodies through Starlette's parsing pipeline.
    """
    app = FastAPI()

    @app.post("/parse")
    async def _parse(request: Request) -> dict:
        parsed = await parse_input_request_from_body(request)
        return parsed.model_dump()

    return app


@pytest.fixture
def parser_client() -> AsyncClient:
    transport = ASGITransport(app=_build_app())
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_multipart_form_data_preserves_session_id_and_input(parser_client: AsyncClient):
    """Multipart form fields must map onto ``SimplifiedAPIRequest`` (regression for #9859)."""
    async with parser_client as client:
        response = await client.post(
            "/parse",
            data={
                "input_value": "Describe this image",
                "session_id": "minha-sessao-reproducao-9859",
                "input_type": "chat",
                "output_type": "chat",
            },
            files={"file": ("image.png", io.BytesIO(b"fake-bytes"), "image/png")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "minha-sessao-reproducao-9859"
    assert payload["input_value"] == "Describe this image"
    assert payload["input_type"] == "chat"
    assert payload["output_type"] == "chat"


@pytest.mark.asyncio
async def test_json_body_preserves_user_id(parser_client: AsyncClient):
    """JSON body ``user_id`` must round-trip into ``SimplifiedAPIRequest`` (regression for #9505)."""
    async with parser_client as client:
        response = await client.post(
            "/parse",
            json={
                "input_value": "What are the recommendations for this user?",
                "user_id": "test123",
                "session_id": "api-test-final",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "test123"
    assert payload["session_id"] == "api-test-final"


@pytest.mark.asyncio
async def test_multipart_form_data_preserves_user_id(parser_client: AsyncClient):
    """Multipart form fields must map ``user_id`` onto ``SimplifiedAPIRequest`` (regression for #9505)."""
    async with parser_client as client:
        response = await client.post(
            "/parse",
            data={
                "input_value": "hello",
                "user_id": "test123",
                "session_id": "api-test-final",
            },
            files={"file": ("a.bin", io.BytesIO(b"bytes"), "application/octet-stream")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "test123"
    assert payload["session_id"] == "api-test-final"


@pytest.mark.asyncio
async def test_multipart_tweaks_parsed_as_json(parser_client: AsyncClient):
    tweaks = {"some-component-id": {"input_value": "abc"}}

    async with parser_client as client:
        response = await client.post(
            "/parse",
            data={
                "input_value": "hello",
                "session_id": "s1",
                "tweaks": orjson.dumps(tweaks).decode(),
            },
            # An attached file forces httpx to send multipart/form-data,
            # mirroring the real-world case from issue #9859 where a file is
            # uploaded inline alongside text fields.
            files={"file": ("a.bin", io.BytesIO(b"bytes"), "application/octet-stream")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tweaks"] == tweaks
    assert payload["session_id"] == "s1"


@pytest.mark.asyncio
async def test_multipart_invalid_tweaks_json_does_not_crash(parser_client: AsyncClient):
    """Malformed tweaks JSON should be ignored, not raise."""
    async with parser_client as client:
        response = await client.post(
            "/parse",
            data={
                "input_value": "hello",
                "session_id": "s1",
                "tweaks": "{not-json",
            },
            files={"file": ("a.bin", io.BytesIO(b"bytes"), "application/octet-stream")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tweaks"] is None
    # Other fields should still be preserved.
    assert payload["input_value"] == "hello"
    assert payload["session_id"] == "s1"


@pytest.mark.asyncio
async def test_multipart_ignores_file_in_known_fields(parser_client: AsyncClient):
    """An uploaded file under a known schema field must not blow up the parser."""
    async with parser_client as client:
        response = await client.post(
            "/parse",
            data={"session_id": "s1"},
            # ``input_value`` is intentionally sent as a file upload to confirm
            # we only consume string-valued form fields.
            files={"input_value": ("a.bin", io.BytesIO(b"bytes"), "application/octet-stream")},
        )

    assert response.status_code == 200
    payload = response.json()
    # input_value is not a string so we drop it (schema default kicks in).
    assert payload["input_value"] is None
    assert payload["session_id"] == "s1"


@pytest.mark.asyncio
async def test_json_body_still_parsed(parser_client: AsyncClient):
    async with parser_client as client:
        response = await client.post(
            "/parse",
            json={
                "input_value": "hi",
                "session_id": "json-session",
                "tweaks": {"x": {"y": 1}},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        **SimplifiedAPIRequest().model_dump(),
        "input_value": "hi",
        "session_id": "json-session",
        "tweaks": {"x": {"y": 1}},
    }


@pytest.mark.asyncio
async def test_empty_body_returns_default(parser_client: AsyncClient):
    async with parser_client as client:
        response = await client.post("/parse")

    assert response.status_code == 200
    assert response.json() == SimplifiedAPIRequest().model_dump()


@pytest.mark.asyncio
async def test_malformed_json_returns_default(parser_client: AsyncClient):
    async with parser_client as client:
        response = await client.post(
            "/parse",
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == SimplifiedAPIRequest().model_dump()
