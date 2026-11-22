"""Tests for MCP reverse proxy support (root_path / X-Forwarded-Prefix).

Covers the fix for https://github.com/langflow-ai/langflow/issues/9797 where MCP
SSE transport breaks when Langflow sits behind a reverse proxy that adds a URL
prefix (basePath).
"""

import pytest
from langflow.api.v1.mcp_projects import get_project_sse, project_sse_transports
from mcp.server.sse import SseServerTransport

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
    """Only URL path prefixes may reach transports through the proxy header."""

    async def _captured_downstream_root_path(self, *, configured_root_path, headers=None):
        from langflow.main import create_app, get_settings_service
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse

        settings = get_settings_service().settings
        original_root_path = settings.root_path
        try:
            settings.root_path = configured_root_path
            app = create_app()
            middleware = next(
                middleware.kwargs["dispatch"]
                for middleware in app.user_middleware
                if middleware.kwargs.get("dispatch", lambda: None).__name__ == "forwarded_prefix_middleware"
            )
            request = Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/api/v1/mcp/sse",
                    "root_path": configured_root_path,
                    "query_string": b"",
                    "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
                }
            )

            async def next_app(request):
                return PlainTextResponse(request.scope.get("root_path", ""))

            response = await middleware(request, next_app)
            return response.body.decode()
        finally:
            settings.root_path = original_root_path

    async def test_no_header_preserves_root_path(self):
        root_path = await self._captured_downstream_root_path(configured_root_path="/enabled")
        assert root_path == "/enabled"

    @pytest.mark.parametrize("prefix", ["/langflow", "/my-prefix", "/tools/langflow/", "/v1.2/~instance_1"])
    async def test_forwarded_prefix_header_sets_downstream_root_path(self, prefix):
        root_path = await self._captured_downstream_root_path(
            configured_root_path="/enabled", headers={"X-Forwarded-Prefix": prefix}
        )
        assert root_path == prefix.rstrip("/")

    async def test_middleware_ignores_header_when_root_path_not_configured(self):
        root_path = await self._captured_downstream_root_path(
            configured_root_path="", headers={"X-Forwarded-Prefix": "/attacker-prefix"}
        )
        assert root_path == ""

    @pytest.mark.parametrize(
        "prefix",
        [
            "https://evil.example",
            "//evil.example",
            "///evil.example",
            r"/\evil.example",
            r"/path\evil.example",
            "/%2f%2fevil.example",
            "/%252f%252fevil.example",
            "/%5cevil.example",
            "/.",
            "/..",
            "/path/../other",
            "/path/./other",
            "/%2e%2e/other",
            "/path?query=1",
            "/path#fragment",
            "not-starting-with-slash",
            "/path//other",
            "/path with spaces",
            "/path\t/other",
            "/path\n/other",
            "",
            "/",
        ],
    )
    async def test_middleware_rejects_invalid_prefix(self, prefix):
        root_path = await self._captured_downstream_root_path(
            configured_root_path="/enabled", headers={"X-Forwarded-Prefix": prefix}
        )
        assert root_path == "/enabled"


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
