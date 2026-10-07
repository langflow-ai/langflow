"""LANGFLOW_MCP_BASE_URL must override the host/port-derived MCP project URL.

In a multi-pod deployment the pod binds 0.0.0.0 (which the builder rewrites to localhost),
so the only way to advertise a routable gateway address is this setting.
"""

from uuid import uuid4

import pytest
from langflow.api.utils.mcp.config_utils import (
    get_project_sse_url,
    get_project_streamable_http_url,
)
from langflow.services.deps import get_settings_service

pytestmark = pytest.mark.asyncio


@pytest.fixture
def project_id():
    return uuid4()


async def test_configured_base_url_is_used_verbatim(project_id, monkeypatch):
    settings = get_settings_service().settings
    # Pod bind host that the builder would otherwise turn into localhost.
    monkeypatch.setattr(settings, "host", "0.0.0.0", raising=False)  # noqa: S104
    monkeypatch.setattr(settings, "mcp_base_url", "https://gw.example.com", raising=False)

    url = await get_project_streamable_http_url(project_id)
    assert url == f"https://gw.example.com/api/v1/mcp/project/{project_id}/streamable"
    assert "localhost" not in url
    assert "0.0.0.0" not in url  # noqa: S104 - asserting the bind address is absent, not binding to it


async def test_configured_base_url_strips_trailing_slash(project_id, monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "https://gw.example.com/", raising=False)

    url = await get_project_streamable_http_url(project_id)
    assert url == f"https://gw.example.com/api/v1/mcp/project/{project_id}/streamable"


async def test_configured_base_url_honours_https_and_path(project_id, monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "https://gw.example.com/langflow", raising=False)

    url = await get_project_sse_url(project_id)
    assert url == f"https://gw.example.com/langflow/api/v1/mcp/project/{project_id}/sse"


async def test_empty_base_url_falls_back_to_host_port(project_id, monkeypatch):
    """Backwards compatibility: unset setting keeps the old host/port behaviour."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "", raising=False)
    monkeypatch.setattr(settings, "host", "example.internal", raising=False)
    monkeypatch.setattr(settings, "port", 7860, raising=False)
    monkeypatch.setattr(settings, "runtime_port", None, raising=False)

    url = await get_project_streamable_http_url(project_id)
    assert url == f"http://example.internal:7860/api/v1/mcp/project/{project_id}/streamable"


async def test_empty_base_url_rewrites_bind_host_to_localhost(project_id, monkeypatch):
    """Backwards compatibility: 0.0.0.0 bind host still collapses to localhost when unset."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "", raising=False)
    monkeypatch.setattr(settings, "host", "0.0.0.0", raising=False)  # noqa: S104
    monkeypatch.setattr(settings, "port", 7860, raising=False)
    monkeypatch.setattr(settings, "runtime_port", None, raising=False)

    url = await get_project_streamable_http_url(project_id)
    assert url == f"http://localhost:7860/api/v1/mcp/project/{project_id}/streamable"


async def test_empty_base_url_sse_falls_back_to_host_port(project_id, monkeypatch):
    """SSE URL also uses host/port fallback when mcp_base_url is unset."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "", raising=False)
    monkeypatch.setattr(settings, "host", "example.internal", raising=False)
    monkeypatch.setattr(settings, "port", 7860, raising=False)
    monkeypatch.setattr(settings, "runtime_port", None, raising=False)

    url = await get_project_sse_url(project_id)
    assert url == f"http://example.internal:7860/api/v1/mcp/project/{project_id}/sse"


async def test_whitespace_only_base_url_falls_back_to_host_port(project_id, monkeypatch):
    """A whitespace-only mcp_base_url is treated as unset and falls back to host/port."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "   ", raising=False)
    monkeypatch.setattr(settings, "host", "example.internal", raising=False)
    monkeypatch.setattr(settings, "port", 7860, raising=False)
    monkeypatch.setattr(settings, "runtime_port", None, raising=False)

    url = await get_project_streamable_http_url(project_id)
    assert url == f"http://example.internal:7860/api/v1/mcp/project/{project_id}/streamable"
