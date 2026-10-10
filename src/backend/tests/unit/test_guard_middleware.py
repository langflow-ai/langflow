"""Unit tests for the optional fastapi-guard middleware wiring."""

import itertools

import pytest
from fastapi import FastAPI
from langflow.services.security import attach_guard

pytest.importorskip("guard")

from httpx import ASGITransport, AsyncClient

# Rate limiting and ban state in fastapi-guard are process-wide, so every
# test drives its own TEST-NET client IP to stay hermetic.
_IP = itertools.count(1)


def _unique_ip() -> str:
    n = next(_IP)
    return f"198.51.{n // 250}.{(n % 250) + 1}"


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    attach_guard(app)
    return app


async def _get(monkeypatch, client_ip, path="/ping", **env):
    monkeypatch.delenv("LANGFLOW_GUARD_ENABLED", raising=False)
    for name in (
        "LANGFLOW_GUARD_BLOCKED_IPS",
        "LANGFLOW_GUARD_RATE_LIMIT",
        "LANGFLOW_GUARD_RATE_LIMIT_WINDOW",
        "LANGFLOW_GUARD_PASSIVE_MODE",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    transport = ASGITransport(app=_build_app(), client=(client_ip, 50000))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


async def test_disabled_by_default(monkeypatch):
    response = await _get(monkeypatch, _unique_ip())
    assert response.status_code == 200


async def test_blocked_ip_is_rejected(monkeypatch):
    blocked = _unique_ip()
    response = await _get(
        monkeypatch,
        blocked,
        LANGFLOW_GUARD_ENABLED="true",
        LANGFLOW_GUARD_BLOCKED_IPS=blocked,
    )
    assert response.status_code == 403


async def test_rate_limit_returns_429(monkeypatch):
    client_ip = _unique_ip()
    env = {
        "LANGFLOW_GUARD_ENABLED": "true",
        "LANGFLOW_GUARD_RATE_LIMIT": "2",
        "LANGFLOW_GUARD_RATE_LIMIT_WINDOW": "60",
    }
    assert (await _get(monkeypatch, client_ip, **env)).status_code == 200
    assert (await _get(monkeypatch, client_ip, **env)).status_code == 200
    assert (await _get(monkeypatch, client_ip, **env)).status_code == 429


async def test_passive_mode_never_blocks(monkeypatch):
    blocked = _unique_ip()
    response = await _get(
        monkeypatch,
        blocked,
        LANGFLOW_GUARD_ENABLED="true",
        LANGFLOW_GUARD_PASSIVE_MODE="true",
        LANGFLOW_GUARD_BLOCKED_IPS=blocked,
    )
    assert response.status_code == 200
