"""Test OpenAI Responses Error Handling."""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langflow.main import create_app
from langflow.schema import OpenAIResponsesRequest


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _mock_api_key_user():
    from datetime import datetime, timezone

    from langflow.services.database.models.user.model import UserRead

    now = datetime.now(timezone.utc)
    return UserRead(
        id="00000000-0000-0000-0000-000000000000",
        username="testuser",
        is_active=True,
        is_superuser=False,
        create_at=now,
        updated_at=now,
        profile_image=None,
        store_api_key=None,
        last_login_at=None,
        optins=None,
    )


def _mock_responses_flow():
    mock_flow = MagicMock()
    mock_flow.id = "11111111-1111-1111-1111-111111111111"
    mock_flow.user_id = "00000000-0000-0000-0000-000000000000"
    mock_flow.workspace_id = None
    mock_flow.folder_id = None
    mock_flow.data = {"nodes": [{"data": {"type": "ChatInput"}}, {"data": {"type": "ChatOutput"}}]}
    return mock_flow


async def _mock_api_key_security():
    return _mock_api_key_user()


@pytest.mark.asyncio
async def test_openai_response_stream_error_handling(client):
    """Test that errors during streaming are correctly propagated to the client.

    Ensure errors are propagated as OpenAI-compatible error responses.
    """
    from langflow.services.auth.utils import api_key_security

    client.app.dependency_overrides[api_key_security] = _mock_api_key_security

    try:
        # Mock the flow execution to simulate an error during streaming
        with (
            patch("langflow.api.v1.openai_responses.get_flow_by_id_or_endpoint_name") as mock_get_flow,
            patch("langflow.api.v1.openai_responses.ensure_flow_permission"),
            patch("langflow.api.v1.openai_responses.run_flow_generator") as _,
            patch("langflow.api.v1.openai_responses.consume_and_yield") as mock_consume,
        ):
            # Setup mock flow
            mock_get_flow.return_value = _mock_responses_flow()

            # We need to simulate the event manager queue behavior
            # The run_flow_generator in the actual code puts events into the event_manager
            # which puts them into the queue.

            # Instead of mocking the complex event manager interaction, we can mock
            # consume_and_yield to yield our simulated error event

            # Simulate an error event from the queue
            error_event = json.dumps({"event": "error", "data": {"error": "Simulated streaming error"}}).encode("utf-8")

            # Yield error event then None to end stream
            async def event_generator(*_, **__):
                yield error_event
                yield None

            mock_consume.side_effect = event_generator

            # Make the request
            response = client.post(
                "/api/v1/responses",
                json={"model": "test-flow-id", "input": "test input", "stream": True},
                headers={"Authorization": "Bearer test-key"},
            )

            # Check response
            assert response.status_code == 200
            content = response.content.decode("utf-8")

            # Verify we got the error event in the stream
            assert (
                "event: error" not in content
            )  # OpenAI format doesn't use event: error for the data payload itself usually, but let's check the data

            # We expect a data line with the error JSON
            # The fix implementation: yield f"data: {json.dumps(error_response)}\n\n"

            assert '"content":"Simulated streaming error"' in content
            assert '"status":"failed"' in content
            assert '"finish_reason":"error"' in content
    finally:
        client.app.dependency_overrides = {}


def test_openai_response_timeout_setting_falls_back_for_none(monkeypatch):
    """A missing/empty worker timeout should not crash Responses requests."""
    from langflow.api.v1 import openai_responses

    settings_service = SimpleNamespace(settings=SimpleNamespace(worker_timeout=None))
    monkeypatch.setattr(openai_responses, "get_settings_service", lambda: settings_service)

    assert openai_responses._get_openai_responses_timeout_seconds() == 300


def test_openai_response_non_streaming_execution_timeout(client):
    """Non-streaming Responses requests should stop at the configured worker timeout."""
    from langflow.services.auth.utils import api_key_security

    client.app.dependency_overrides[api_key_security] = _mock_api_key_security

    try:

        async def slow_simple_run_flow(*_, **__):
            await asyncio.sleep(0.2)

        with (
            patch("langflow.api.v1.openai_responses.get_flow_by_id_or_endpoint_name") as mock_get_flow,
            patch("langflow.api.v1.openai_responses.ensure_flow_permission"),
            patch("langflow.api.v1.openai_responses.simple_run_flow", side_effect=slow_simple_run_flow),
            patch("langflow.api.v1.openai_responses.get_settings_service") as mock_get_settings_service,
        ):
            mock_get_flow.return_value = _mock_responses_flow()
            mock_get_settings_service.return_value.settings.worker_timeout = 0.01

            start = time.perf_counter()
            response = client.post(
                "/api/v1/responses",
                json={"model": "test-flow-id", "input": "test input", "stream": False},
                headers={"Authorization": "Bearer test-key"},
            )
            elapsed = time.perf_counter() - start

            assert elapsed < 0.2
            assert response.status_code == 200
            content = response.json()
            assert content["error"]["type"] == "request_timeout"
            assert content["error"]["code"] == "request_timeout"
            assert "exceeded 0.01 seconds" in content["error"]["message"]
    finally:
        client.app.dependency_overrides = {}


def test_openai_response_non_streaming_provider_timeout_is_reported_as_provider_error(client):
    """Provider-raised TimeoutError should not be mislabeled as the non-streaming endpoint deadline."""
    from langflow.services.auth.utils import api_key_security

    client.app.dependency_overrides[api_key_security] = _mock_api_key_security

    try:

        async def provider_timeout_simple_run_flow(*_, **__):
            msg = "provider timed out before returning"
            raise TimeoutError(msg)

        with (
            patch("langflow.api.v1.openai_responses.get_flow_by_id_or_endpoint_name") as mock_get_flow,
            patch("langflow.api.v1.openai_responses.ensure_flow_permission"),
            patch("langflow.api.v1.openai_responses.simple_run_flow", side_effect=provider_timeout_simple_run_flow),
            patch("langflow.api.v1.openai_responses.get_settings_service") as mock_get_settings_service,
        ):
            mock_get_flow.return_value = _mock_responses_flow()
            mock_get_settings_service.return_value.settings.worker_timeout = 30

            response = client.post(
                "/api/v1/responses",
                json={"model": "test-flow-id", "input": "test input", "stream": False},
                headers={"Authorization": "Bearer test-key"},
            )

            assert response.status_code == 200
            content = response.json()
            assert content["error"]["type"] == "processing_error"
            assert content["error"]["message"] == "provider timed out before returning"
            assert content["error"].get("code") != "request_timeout"
            assert "OpenAI Responses request exceeded" not in content["error"]["message"]
    finally:
        client.app.dependency_overrides = {}


def test_openai_response_streaming_execution_timeout_emits_error_chunk_and_cancels_flow(client):
    """Streaming Responses requests should fail with structured SSE and stop the producer task."""
    from langflow.services.auth.utils import api_key_security

    client.app.dependency_overrides[api_key_security] = _mock_api_key_security
    try:
        run_flow_cancelled = False

        async def slow_run_flow_generator(*_, **__):
            nonlocal run_flow_cancelled
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                run_flow_cancelled = True
                raise

        async def stalled_stream_events(*_, **__):
            await asyncio.sleep(0.2)
            yield None

        with (
            patch("langflow.api.v1.openai_responses.get_flow_by_id_or_endpoint_name") as mock_get_flow,
            patch("langflow.api.v1.openai_responses.ensure_flow_permission"),
            patch("langflow.api.v1.openai_responses.run_flow_generator", side_effect=slow_run_flow_generator),
            patch("langflow.api.v1.openai_responses.consume_and_yield", side_effect=stalled_stream_events),
            patch("langflow.api.v1.openai_responses.get_settings_service") as mock_get_settings_service,
        ):
            mock_get_flow.return_value = _mock_responses_flow()
            mock_get_settings_service.return_value.settings.worker_timeout = 0.01

            response = client.post(
                "/api/v1/responses",
                json={"model": "test-flow-id", "input": "test input", "stream": True},
                headers={"Authorization": "Bearer test-key"},
            )

            assert response.status_code == 200
            content = response.content.decode("utf-8")
            timeout_chunk = json.loads(content.split("data: ")[2].split("\n\n")[0])
            assert "event: response.failed" not in content
            assert timeout_chunk["object"] == "response.chunk"
            assert timeout_chunk["status"] == "failed"
            assert timeout_chunk["finish_reason"] == "error"
            assert timeout_chunk["delta"]["content"] == "OpenAI Responses request exceeded 0.01 seconds"
            assert content.rstrip().endswith("data: [DONE]")
            assert run_flow_cancelled is True
    finally:
        client.app.dependency_overrides = {}


def test_openai_response_streaming_provider_timeout_is_reported_as_provider_error(client):
    """Provider-raised TimeoutError should not be mislabeled as the endpoint deadline."""
    from langflow.services.auth.utils import api_key_security

    client.app.dependency_overrides[api_key_security] = _mock_api_key_security
    try:

        async def run_flow_generator_noop(*_, **__) -> None:
            return None

        async def provider_timeout_stream_events(*_, **__):
            msg = "provider timed out while streaming"
            raise TimeoutError(msg)
            yield None

        with (
            patch("langflow.api.v1.openai_responses.get_flow_by_id_or_endpoint_name") as mock_get_flow,
            patch("langflow.api.v1.openai_responses.ensure_flow_permission"),
            patch("langflow.api.v1.openai_responses.run_flow_generator", side_effect=run_flow_generator_noop),
            patch("langflow.api.v1.openai_responses.consume_and_yield", side_effect=provider_timeout_stream_events),
            patch("langflow.api.v1.openai_responses.get_settings_service") as mock_get_settings_service,
        ):
            mock_get_flow.return_value = _mock_responses_flow()
            mock_get_settings_service.return_value.settings.worker_timeout = 30

            response = client.post(
                "/api/v1/responses",
                json={"model": "test-flow-id", "input": "test input", "stream": True},
                headers={"Authorization": "Bearer test-key"},
            )

            assert response.status_code == 200
            content = response.content.decode("utf-8")
            error_chunk = json.loads(content.split("data: ")[2].split("\n\n")[0])
            assert error_chunk["status"] == "failed"
            assert error_chunk["finish_reason"] == "error"
            assert error_chunk["delta"]["content"] == "provider timed out while streaming"
            assert "OpenAI Responses request exceeded" not in content
    finally:
        client.app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_openai_response_streaming_client_cancellation_cancels_pending_event_read():
    """Client cancellation should not leave the pending stream event read running."""
    from langflow.api.v1.openai_responses import run_flow_for_openai_responses

    event_read_started = asyncio.Event()
    event_read_cancelled = asyncio.Event()

    async def slow_run_flow_generator(*_, **__):
        await asyncio.sleep(10)

    async def pending_stream_events(*_, **__):
        try:
            event_read_started.set()
            await asyncio.sleep(10)
            yield None
        except asyncio.CancelledError:
            event_read_cancelled.set()
            raise

    with (
        patch("langflow.api.v1.openai_responses.run_flow_generator", side_effect=slow_run_flow_generator),
        patch("langflow.api.v1.openai_responses.consume_and_yield", side_effect=pending_stream_events),
    ):
        streaming_response = await run_flow_for_openai_responses(
            flow=_mock_responses_flow(),
            request=OpenAIResponsesRequest(model="test-flow-id", input="test input", stream=True),
            api_key_user=_mock_api_key_user(),
            stream=True,
            timeout_seconds=30,
        )

        stream_iterator = streaming_response.body_iterator
        first_chunk = await stream_iterator.__anext__()
        assert first_chunk.startswith("data: ")

        next_chunk_task = asyncio.create_task(stream_iterator.__anext__())
        await asyncio.wait_for(event_read_started.wait(), timeout=1)

        next_chunk_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await next_chunk_task

        await asyncio.wait_for(event_read_cancelled.wait(), timeout=1)
