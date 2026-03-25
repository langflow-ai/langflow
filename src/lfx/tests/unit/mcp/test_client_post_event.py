"""Tests for LangflowClient.post_event -- best-effort event emission."""

from unittest.mock import AsyncMock, patch

import pytest
from lfx.mcp.client import LangflowClient


@pytest.fixture
def client():
    return LangflowClient(server_url="http://localhost:7860", api_key="test-key")  # pragma: allowlist secret


class TestPostEvent:
    async def test_post_event_calls_post_with_correct_payload(self, client):
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.post_event("flow-123", "component_added", "Added OpenAI")

            mock_post.assert_called_once_with(
                "/flows/flow-123/events",
                json_data={"type": "component_added", "summary": "Added OpenAI"},
            )

    async def test_post_event_default_summary_is_empty(self, client):
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.post_event("flow-123", "component_added")

            mock_post.assert_called_once_with(
                "/flows/flow-123/events",
                json_data={"type": "component_added", "summary": ""},
            )

    async def test_post_event_suppresses_exceptions(self, client):
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = RuntimeError("POST /flows/flow-123/events failed (500)")

            # Should not raise
            await client.post_event("flow-123", "component_added", "Added OpenAI")

    async def test_post_event_suppresses_connection_errors(self, client):
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = ConnectionError("Connection refused")

            await client.post_event("flow-123", "component_added")
