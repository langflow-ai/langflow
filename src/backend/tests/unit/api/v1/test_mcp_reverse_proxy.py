"""Tests for MCP reverse proxy support (root_path / X-Forwarded-Prefix).

Covers the fix for https://github.com/langflow-ai/langflow/issues/9797 where MCP
SSE transport breaks when Langflow sits behind a reverse proxy that adds a URL
prefix (basePath).
"""

from unittest.mock import patch

import pytest
from langflow.api.v1.mcp_projects import get_project_sse, project_sse_transports
from mcp.server.sse import SseServerTransport

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Unit: SseServerTransport respects root_path in the ASGI scope
# ---------------------------------------------------------------------------


class TestSseTransportRootPath:
    """Verify that the MCP SDK's SseServerTransport prepends root_path."""

    @pytest.fixture
    def transport(self):
        return SseServerTransport("/api/v1/mcp/")

    def test_endpoint_stored(self, transport):
        assert transport._endpoint == "/api/v1/mcp/"

    def test_project_transport_endpoint(self):
        """get_project_sse stores the correct endpoint path."""
        from uuid import uuid4

        project_id = uuid4()
        project_id_str = str(project_id)

        # Clean up after the test
        try:
            sse = get_project_sse(project_id)
            assert sse._endpoint == f"/api/v1/mcp/project/{project_id_str}/"
        finally:
            project_sse_transports.pop(project_id_str, None)


# ---------------------------------------------------------------------------
# Unit: X-Forwarded-Prefix middleware
# ---------------------------------------------------------------------------


class TestForwardedPrefixMiddleware:
    """Test that the middleware propagates X-Forwarded-Prefix to scope root_path."""

    @pytest.fixture
    def _mock_settings_root_path(self):
        """Ensure root_path setting is empty so we isolate the header test."""
        with patch("langflow.main.get_settings_service") as mock_svc:
            mock_svc.return_value.settings.root_path = ""
            yield

    async def test_no_header_preserves_root_path(self, client):
        """Without X-Forwarded-Prefix the root_path stays unchanged."""
        response = await client.head("api/v1/mcp/sse")
        assert response.status_code == 200

    async def test_forwarded_prefix_header_is_accepted(self, client):
        """X-Forwarded-Prefix header does not break the request."""
        response = await client.head(
            "api/v1/mcp/sse",
            headers={"X-Forwarded-Prefix": "/my-prefix"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Unit: root_path setting
# ---------------------------------------------------------------------------


class TestRootPathSetting:
    """Test that the root_path setting exists and defaults to empty."""

    def test_root_path_default_empty(self):
        from lfx.services.settings.base import Settings

        s = Settings()
        assert s.root_path == ""

    def test_root_path_can_be_set(self, monkeypatch):
        from lfx.services.settings.base import Settings

        monkeypatch.setenv("LANGFLOW_ROOT_PATH", "/basePath")
        s = Settings()
        assert s.root_path == "/basePath"
