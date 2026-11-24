"""The legacy SSE transport must be switchable off without touching Streamable HTTP.

``mcp_server_enabled`` mounts both transports, so a deployment that wants only the
modern transport had no lever. ``mcp_sse_enabled`` closes SSE and its message endpoint
while Streamable HTTP keeps serving.
"""

import pytest
from fastapi import HTTPException
from langflow.api.v1 import mcp as mcp_module
from langflow.api.v1 import mcp_projects as mcp_projects_module
from langflow.api.v1.mcp_utils import raise_if_sse_disabled
from lfx.services.deps import get_settings_service

SSE_PATHS = {"/api/v1/mcp/sse", "/api/v1/mcp/", "/api/v1/mcp/project/{project_id}/sse"}


@pytest.fixture
def sse_disabled():
    settings = get_settings_service().settings
    original = settings.mcp_sse_enabled
    settings.mcp_sse_enabled = False
    try:
        yield
    finally:
        settings.mcp_sse_enabled = original


def test_should_allow_sse_when_enabled_by_default():
    """Default stays permissive so existing SSE clients keep working."""
    assert get_settings_service().settings.mcp_sse_enabled is True
    assert raise_if_sse_disabled() is None


@pytest.mark.usefixtures("sse_disabled")
def test_should_reject_sse_with_404_when_disabled():
    """404 rather than 403: a disabled transport should look absent, not forbidden."""
    with pytest.raises(HTTPException) as exc_info:
        raise_if_sse_disabled()

    assert exc_info.value.status_code == 404
    assert "Streamable HTTP" in exc_info.value.detail


def _dependency_calls(router, path: str, method: str) -> list:
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return [dep.call for dep in route.dependant.dependencies]
    msg = f"route {method} {path} not found"
    raise AssertionError(msg)


@pytest.mark.parametrize(
    ("router", "path", "method"),
    [
        (mcp_module.router, "/mcp/sse", "GET"),
        (mcp_module.router, "/mcp/sse", "HEAD"),
        (mcp_module.router, "/mcp/", "POST"),
        (mcp_projects_module.router, "/mcp/project/{project_id}/sse", "GET"),
        (mcp_projects_module.router, "/mcp/project/{project_id}/sse", "HEAD"),
        (mcp_projects_module.router, "/mcp/project/{project_id}", "POST"),
        (mcp_projects_module.router, "/mcp/project/{project_id}/", "POST"),
    ],
)
def test_should_guard_every_sse_route(router, path, method):
    """Every SSE-transport route, including the POST message endpoint, honours the flag."""
    assert raise_if_sse_disabled in _dependency_calls(router, path, method)


@pytest.mark.parametrize(
    ("router", "path"),
    [
        (mcp_module.router, "/mcp/streamable"),
        (mcp_projects_module.router, "/mcp/project/{project_id}/streamable"),
    ],
)
def test_should_leave_streamable_http_unguarded(router, path):
    """Streamable HTTP must stay mounted regardless of the SSE flag."""
    guarded = [
        dep.call
        for route in router.routes
        if getattr(route, "path", None) == path
        for dep in route.dependant.dependencies
    ]

    assert raise_if_sse_disabled not in guarded
