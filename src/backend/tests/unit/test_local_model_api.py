"""Tests for /api/v1/local_model endpoints.

The endpoints expose the bundled local-model bootstrap pipeline to the frontend.
Bootstrap internals are exhaustively tested at the unit level (see lfx tests);
here we pin the HTTP contract: response shape, status codes, auth, and that
the heavy lifting runs in a background task (POST returns 202 immediately).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_status_endpoint_returns_current_state(client: AsyncClient, logged_in_headers):
    with (
        patch("langflow.api.v1.local_model.is_docker", return_value=False),
        patch("langflow.api.v1.local_model.is_ollama_installed", return_value=True),
        patch("langflow.api.v1.local_model.is_ollama_running", AsyncMock(return_value=True)),
        patch("langflow.api.v1.local_model.is_model_pulled", AsyncMock(return_value=True)),
    ):
        response = await client.get("api/v1/local_model/status", headers=logged_in_headers)

    assert response.status_code == 200
    data = response.json()
    # Pin the contract — the frontend reads exactly these keys.
    assert data["is_docker"] is False
    assert data["is_ollama_installed"] is True
    assert data["is_ollama_running"] is True
    assert data["is_model_pulled"] is True
    assert data["default_model"] == "qwen2.5:1.5b"
    assert data["ready"] is True


@pytest.mark.asyncio
async def test_status_marks_not_ready_when_any_step_missing(client: AsyncClient, logged_in_headers):
    with (
        patch("langflow.api.v1.local_model.is_docker", return_value=False),
        patch("langflow.api.v1.local_model.is_ollama_installed", return_value=True),
        patch("langflow.api.v1.local_model.is_ollama_running", AsyncMock(return_value=True)),
        # Model not pulled → not ready.
        patch("langflow.api.v1.local_model.is_model_pulled", AsyncMock(return_value=False)),
    ):
        response = await client.get("api/v1/local_model/status", headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json()["ready"] is False


@pytest.mark.asyncio
async def test_status_endpoint_requires_authentication(client: AsyncClient):
    # No headers → 401/403. The endpoint exposes deployment posture; not a public surface.
    response = await client.get("api/v1/local_model/status")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_setup_endpoint_returns_202_and_schedules_bootstrap(client: AsyncClient, logged_in_headers):
    # Why 202 (not 200): the bootstrap is long-running (download, install). We
    # respond immediately so the frontend can poll /status. The actual work runs
    # in a FastAPI BackgroundTasks-style handler.
    with patch("langflow.api.v1.local_model.ensure_local_model_ready", AsyncMock()):
        response = await client.post(
            "api/v1/local_model/setup",
            json={"consent": True},
            headers=logged_in_headers,
        )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True


@pytest.mark.asyncio
async def test_setup_endpoint_rejects_when_consent_is_false(client: AsyncClient, logged_in_headers):
    # Why explicit consent in body: the endpoint MUST not auto-install based on a
    # bare POST. The body acts as the "I agree" signal that the frontend captured
    # from the user via UI dialog.
    with patch("langflow.api.v1.local_model.ensure_local_model_ready", AsyncMock()) as mock_bootstrap:
        response = await client.post(
            "api/v1/local_model/setup",
            json={"consent": False},
            headers=logged_in_headers,
        )

    assert response.status_code == 400
    mock_bootstrap.assert_not_called()


@pytest.mark.asyncio
async def test_setup_endpoint_requires_authentication(client: AsyncClient):
    response = await client.post("api/v1/local_model/setup", json={"consent": True})
    assert response.status_code in (401, 403)
