"""``POST /api/v1/agentic/assist/run`` — the headless (auto-apply) assistant route.

The UI's ``/assist/stream`` deliberately does NOT persist: the user approves the
proposed canvas in a card first. A headless caller (the MCP tool) has no such
card, so its canvas edits would be dropped. This route runs the assistant with
``apply_edits_immediately`` through ``run_assistant_and_persist`` and streams the
same progress events, ending in a ``complete`` event carrying the persisted result.
"""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

MODULE = "langflow.agentic.utils.assistant_runner"

pytestmark = pytest.mark.asyncio


@pytest.fixture
def agentic_enabled(client):  # noqa: ARG001 — the app must exist first
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    original = settings.agentic_experience
    settings.agentic_experience = True
    yield
    settings.agentic_experience = original


def _sse_events(body: str) -> list[dict]:
    return [json.loads(line[5:].strip()) for line in body.splitlines() if line.startswith("data:")]


@pytest.mark.usefixtures("agentic_enabled")
class TestAssistHeadlessRoute:
    async def test_should_persist_and_stream_progress_then_complete(self, client: AsyncClient, logged_in_headers):
        flow_id = str(uuid4())

        async def fake_persist(*, on_progress=None, **_kwargs):
            if on_progress is not None:
                await on_progress({"event": "progress", "step": "building", "message": "Building flow"})
            return {
                "flow_id": flow_id,
                "link": f"/flow/{flow_id}",
                "result": "done",
                "error": None,
                "flow_changed": True,
                "session_id": "s-1",
                "provider": "OpenAI",
                "model_name": "gpt-5.5",
            }

        with patch(f"{MODULE}.run_assistant_and_persist", new=AsyncMock(side_effect=fake_persist)):
            response = await client.post(
                "api/v1/agentic/assist/run",
                headers=logged_in_headers,
                json={"instruction": "build a chat flow"},
            )

        assert response.status_code == status.HTTP_200_OK
        events = _sse_events(response.text)
        kinds = [e.get("event") for e in events]
        assert "progress" in kinds
        assert kinds[-1] == "complete"
        payload = events[-1]["data"]
        assert payload["flow_id"] == flow_id
        assert payload["flow_changed"] is True
        assert payload["result"] == "done"

    async def test_should_forward_the_optional_flow_and_model_context(self, client: AsyncClient, logged_in_headers):
        captured = {}

        async def fake_persist(**kwargs):
            captured.update(kwargs)
            return {"flow_id": str(uuid4()), "result": "ok", "flow_changed": False}

        with (
            patch(f"{MODULE}.run_assistant_and_persist", new=AsyncMock(side_effect=fake_persist)),
            patch("langflow.agentic.api.router._validate_flow_access", new=AsyncMock()),
        ):
            await client.post(
                "api/v1/agentic/assist/run",
                headers=logged_in_headers,
                json={
                    "instruction": "edit it",
                    "flow_id": "11111111-1111-4111-8111-111111111111",
                    "provider": "OpenAI",
                    "model_name": "gpt-5.5",
                    "session_id": "sess-9",
                },
            )

        assert captured["instruction"] == "edit it"
        assert captured["flow_id"] == "11111111-1111-4111-8111-111111111111"
        assert captured["provider"] == "OpenAI"
        assert captured["model_name"] == "gpt-5.5"
        assert captured["session_id"] == "sess-9"

    async def test_should_surface_a_run_failure_as_an_error_event(self, client: AsyncClient, logged_in_headers):
        with patch(
            f"{MODULE}.run_assistant_and_persist",
            new=AsyncMock(side_effect=RuntimeError("assistant exploded")),
        ):
            response = await client.post(
                "api/v1/agentic/assist/run",
                headers=logged_in_headers,
                json={"instruction": "boom"},
            )

        assert response.status_code == status.HTTP_200_OK
        events = _sse_events(response.text)
        assert events[-1]["event"] == "error"
        assert "assistant exploded" in json.dumps(events[-1])


class TestAssistHeadlessRouteAuth:
    async def test_should_reject_unauthenticated(self, client: AsyncClient):
        response = await client.post("api/v1/agentic/assist/run", json={"instruction": "hi"})
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
