"""Test OpenAI Responses Error Handling."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langflow.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_openai_response_stream_error_handling(client):
    """Test that errors during streaming are correctly propagated to the client.

    Ensure errors are propagated as OpenAI-compatible error responses.
    """
    # Mock api_key_security dependency
    from langflow.services.auth.utils import api_key_security
    from langflow.services.database.models.user.model import UserRead

    async def mock_api_key_security():
        from datetime import datetime, timezone

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

    client.app.dependency_overrides[api_key_security] = mock_api_key_security

    # Mock the flow execution to simulate an error during streaming
    with (
        patch("langflow.api.v1.openai_responses.get_flow_by_id_or_endpoint_name") as mock_get_flow,
        patch("langflow.api.v1.openai_responses.run_flow_generator") as _,
        patch("langflow.api.v1.openai_responses.consume_and_yield") as mock_consume,
    ):
        # Setup mock flow
        mock_flow = MagicMock()
        mock_flow.data = {"nodes": [{"data": {"type": "ChatInput"}}, {"data": {"type": "ChatOutput"}}]}
        mock_get_flow.return_value = mock_flow

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

        expected_error_part = '"message": "Simulated streaming error"'
        assert expected_error_part in content
        assert '"type": "processing_error"' in content

    # Clean up overrides
    client.app.dependency_overrides = {}
