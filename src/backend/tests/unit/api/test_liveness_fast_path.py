"""GET /health is answered before the middleware stack; every other request passes through."""

from __future__ import annotations

import httpx
import pytest
from langflow.api.health_check_router import LivenessFastPath


async def _inner(scope, _receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 299, "headers": []})
    await send({"type": "http.response.body", "body": b"inner"})


@pytest.fixture
def client():
    calls: list[str] = []

    async def counting(scope, receive, send):
        calls.append(f"{scope['method']} {scope['path']}")
        await _inner(scope, receive, send)

    transport = httpx.ASGITransport(app=LivenessFastPath(counting))
    return httpx.AsyncClient(transport=transport, base_url="http://test"), calls


async def test_health_is_answered_without_the_inner_app(client):
    http, calls = client
    async with http:
        response = await http.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"] == "application/json"
    assert calls == []


@pytest.mark.parametrize(("method", "path"), [("GET", "/healthz"), ("GET", "/health_check"), ("POST", "/health")])
async def test_other_requests_pass_through(client, method, path):
    http, calls = client
    async with http:
        response = await http.request(method, path)
    assert response.status_code == 299
    assert calls == [f"{method} {path}"]


async def test_app_answers_health_like_the_route():
    from langflow.main import create_app

    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/health")
    assert response.status_code == 200
    assert response.content == b'{"status":"ok"}'
