import json

import pytest
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from langflow.main import GZIP_COMPRESS_LEVEL, GZIP_EXCLUDED_CONTENT_TYPES, GZIP_MINIMUM_SIZE
from starlette.middleware.gzip import GZipMiddleware

LARGE_NODE_COUNT = 40


def _large_flow_payload() -> dict:
    nodes = [
        {
            "id": f"node-{index}",
            "data": {"node": {"template": {"code": {"value": "from lfx.custom import Component\n" * 12}}}},
        }
        for index in range(LARGE_NODE_COUNT)
    ]
    return {
        "name": "compression fixture",
        "description": "flow large enough to cross the compression threshold",
        "data": {"nodes": nodes, "edges": []},
        "is_component": False,
        "webhook": False,
    }


async def _create_large_flow(client: AsyncClient, headers: dict) -> str:
    payload = _large_flow_payload()
    assert len(json.dumps(payload).encode()) > GZIP_MINIMUM_SIZE
    response = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def test_flow_read_is_compressed_when_the_client_accepts_gzip(client: AsyncClient, logged_in_headers):
    flow_id = await _create_large_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/flows/{flow_id}", headers={**logged_in_headers, "Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in response.headers["vary"].lower()
    assert response.json()["id"] == flow_id


async def test_flow_read_is_untouched_when_the_client_does_not_accept_gzip(client: AsyncClient, logged_in_headers):
    flow_id = await _create_large_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/flows/{flow_id}", headers={**logged_in_headers, "Accept-Encoding": "identity"})

    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert json.loads(response.content)["id"] == flow_id


async def test_flow_update_echo_is_compressed(client: AsyncClient, logged_in_headers):
    flow_id = await _create_large_flow(client, logged_in_headers)
    payload = _large_flow_payload()
    payload["name"] = "compression fixture renamed"

    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json=payload,
        headers={**logged_in_headers, "Accept-Encoding": "gzip"},
    )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.json()["name"] == "compression fixture renamed"


async def test_response_below_the_threshold_is_not_compressed(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/version", headers={**logged_in_headers, "Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert len(response.content) < GZIP_MINIMUM_SIZE
    assert "content-encoding" not in response.headers


EXCLUDED_UNDER_TEST = (
    "application/octet-stream",
    "application/zip",
    "text/event-stream",
    "image/png",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
)


def _app_with_the_same_middleware() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        GZipMiddleware,
        minimum_size=GZIP_MINIMUM_SIZE,
        compresslevel=GZIP_COMPRESS_LEVEL,
        exclude_content_types=GZIP_EXCLUDED_CONTENT_TYPES,
    )

    @app.get("/payload")
    async def payload(content_type: str) -> Response:
        return Response(content=b"x" * (GZIP_MINIMUM_SIZE * 4), media_type=content_type)

    @app.get("/stream")
    async def stream(content_type: str, events: int) -> StreamingResponse:
        async def emit():
            for index in range(events):
                yield (json.dumps({"event": "end_vertex", "id": index}) + "\n\n").encode()

        return StreamingResponse(emit(), media_type=content_type)

    return app


def test_binary_and_streaming_content_types_are_configured_as_excluded():
    for content_type in EXCLUDED_UNDER_TEST:
        assert content_type in GZIP_EXCLUDED_CONTENT_TYPES


@pytest.mark.parametrize("content_type", EXCLUDED_UNDER_TEST)
async def test_excluded_content_types_are_not_compressed(content_type):
    transport = ASGITransport(app=_app_with_the_same_middleware())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/payload", params={"content_type": content_type}, headers={"Accept-Encoding": "gzip"}
        )

    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert len(response.content) == GZIP_MINIMUM_SIZE * 4


async def test_a_compressible_type_on_the_same_app_is_compressed():
    transport = ASGITransport(app=_app_with_the_same_middleware())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/payload", params={"content_type": "application/json"}, headers={"Accept-Encoding": "gzip"}
        )

    assert response.headers["content-encoding"] == "gzip"


async def _stream_response(content_type: str, events: int):
    transport = ASGITransport(app=_app_with_the_same_middleware())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(
            "/stream",
            params={"content_type": content_type, "events": events},
            headers={"Accept-Encoding": "gzip"},
        )


async def test_ndjson_event_streams_are_compressed():
    response = await _stream_response("application/x-ndjson", events=200)

    assert response.headers["content-encoding"] == "gzip"
    assert "content-length" not in response.headers


async def test_a_stream_under_the_size_floor_is_compressed_like_any_other():
    response = await _stream_response("application/x-ndjson", events=1)

    assert len(response.content) < GZIP_MINIMUM_SIZE
    assert response.headers["content-encoding"] == "gzip"


async def test_an_excluded_content_type_is_not_compressed_when_streamed():
    response = await _stream_response("text/event-stream", events=200)

    assert "content-encoding" not in response.headers


def test_gzip_is_registered_innermost():
    from langflow.main import create_app

    assert create_app().user_middleware[-1].cls is GZipMiddleware
