"""Tests for LangflowClient.post_event -- best-effort event emission."""

from unittest.mock import AsyncMock, patch

import pytest
from lfx.mcp.client import LangflowClient


@pytest.fixture
def client():
    return LangflowClient(server_url="http://localhost:7860", api_key="test-key")  # pragma: allowlist secret


class TestPostEvent:
    async def test_posts_to_correct_endpoint_with_payload(self, client):
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.post_event("flow-123", "component_added", "Added OpenAI")

            mock_post.assert_called_once_with(
                "/flows/flow-123/events",
                json_data={"type": "component_added", "summary": "Added OpenAI"},
            )

    async def test_summary_defaults_to_empty_string(self, client):
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.post_event("flow-123", "component_added")

            _, kwargs = mock_post.call_args
            assert kwargs["json_data"]["summary"] == ""

    async def test_never_raises_on_failure(self, client):
        """The core contract: post_event must not break the calling MCP tool."""
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            for exc in [RuntimeError("500"), ConnectionError("refused"), TimeoutError("timeout")]:
                mock_post.side_effect = exc
                await client.post_event("flow-123", "component_added")  # should not raise
