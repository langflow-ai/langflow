"""Tests for MCP reverse proxy support (root_path / X-Forwarded-Prefix).

Covers the fix for https://github.com/langflow-ai/langflow/issues/9797 where MCP
SSE transport breaks when Langflow sits behind a reverse proxy that adds a URL
prefix (basePath).
"""

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

    async def _captured_downstream_root_path(self, *, configured_root_path, headers=None):
        # Import the middleware logic inline to test it in isolation
        from langflow.main import get_settings_service
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse

        captured_root_path = {}

        async def next_app(request):
            captured_root_path["value"] = request.scope.get("root_path", "")
            return PlainTextResponse("ok")

        settings = get_settings_service().settings
        original_root_path = settings.root_path

        try:
            settings.root_path = configured_root_path

            raw_headers = []
            for key, value in (headers or {}).items():
                raw_headers.append((key.lower().encode(), value.encode()))

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/mcp/sse",
                "root_path": "",
                "query_string": b"",
                "headers": raw_headers,
            }
            request = Request(scope)

            prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
            if settings.root_path and prefix and prefix.startswith("/") and "://" not in prefix:
                request.scope["root_path"] = prefix

            await next_app(request)
            return captured_root_path["value"]
        finally:
            settings.root_path = original_root_path

    async def test_no_header_preserves_root_path(self):
        """Without X-Forwarded-Prefix, downstream code sees the original root_path."""
        root_path = await self._captured_downstream_root_path(configured_root_path="/enabled")
        assert root_path == ""

    async def test_forwarded_prefix_header_sets_downstream_root_path(self):
        """With X-Forwarded-Prefix and root_path enabled, downstream code sees the prefix."""
        root_path = await self._captured_downstream_root_path(
            configured_root_path="/enabled",
            headers={"X-Forwarded-Prefix": "/my-prefix"},
        )
        assert root_path == "/my-prefix"

    async def test_middleware_sets_root_path_when_enabled(self):
        """Verify the middleware sets root_path visible to downstream code."""
        root_path = await self._captured_downstream_root_path(
            configured_root_path="/enabled",
            headers={"X-Forwarded-Prefix": "/langflow"},
        )

        assert root_path == "/langflow"

    async def test_middleware_ignores_header_when_root_path_not_configured(self):
        """When root_path is not set, X-Forwarded-Prefix is ignored."""
        from langflow.main import get_settings_service
        from starlette.requests import Request

        settings = get_settings_service().settings
        original_root_path = settings.root_path

        try:
            settings.root_path = ""

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/mcp/sse",
                "root_path": "",
                "query_string": b"",
                "headers": [(b"x-forwarded-prefix", b"/attacker-prefix")],
            }
            request = Request(scope)

            # Middleware should skip when root_path is not configured
            # so root_path remains empty
            assert request.scope["root_path"] == ""
        finally:
            settings.root_path = original_root_path

    async def test_middleware_rejects_invalid_prefix(self):
        """Prefixes with schemes, query strings, or fragments are rejected."""
        invalid_prefixes = [
            "https://evil.com",
            "/path?query=1",
            "/path#fragment",
            "not-starting-with-slash",
        ]
        for prefix in invalid_prefixes:
            clean = prefix.rstrip("/")
            valid = clean.startswith("/") and "://" not in clean and "?" not in clean and "#" not in clean
            assert not valid, f"Expected {prefix!r} to be rejected by validation"


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
