"""MCP Composer must connect to the pod-local Langflow, not the advertised gateway.

``LANGFLOW_MCP_BASE_URL`` names the address *clients* should reach. The composer is a
subprocess of this very process and registers the project endpoint as an upstream member
server it dials itself, so feeding it the gateway URL sends pod-local traffic out through
the ingress and back — which in a multi-pod deployment lands on a different pod, or on a
TLS/auth boundary that rejects it.
"""

from uuid import uuid4

import pytest
from langflow.api.utils.mcp.config_utils import get_project_streamable_http_url
from langflow.api.v1 import mcp_projects
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def gateway_settings(monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "mcp_base_url", "https://gw.example.com", raising=False)
    monkeypatch.setattr(settings, "host", "0.0.0.0", raising=False)  # noqa: S104
    monkeypatch.setattr(settings, "port", 7860, raising=False)
    monkeypatch.setattr(settings, "runtime_port", None, raising=False)
    return settings


@pytest.fixture
def captured_composer(monkeypatch):
    captured: dict[str, str | None] = {}

    class FakeComposerService:
        async def start_project_composer(self, project_id, streamable_http_url, auth_config, *, legacy_sse_url=None):  # noqa: ARG002
            captured["streamable_http_url"] = streamable_http_url
            captured["legacy_sse_url"] = legacy_sse_url

    monkeypatch.setattr(mcp_projects, "get_service", lambda _service_type: FakeComposerService())
    return captured


@pytest.mark.usefixtures("gateway_settings")
async def test_composer_upstream_uses_local_url_not_gateway(project_id, captured_composer):
    await mcp_projects.get_or_start_mcp_composer({"auth_type": "oauth"}, "proj", project_id)

    assert captured_composer["streamable_http_url"] == (
        f"http://localhost:7860/api/v1/mcp/project/{project_id}/streamable"
    )
    assert captured_composer["legacy_sse_url"] == f"http://localhost:7860/api/v1/mcp/project/{project_id}/sse"


@pytest.mark.usefixtures("gateway_settings")
async def test_register_project_with_composer_uses_local_url(project_id, captured_composer):
    project = Folder(id=project_id, name="proj", auth_settings={"auth_type": "oauth"})

    await mcp_projects.register_project_with_composer(project)

    assert captured_composer["streamable_http_url"] == (
        f"http://localhost:7860/api/v1/mcp/project/{project_id}/streamable"
    )


@pytest.mark.usefixtures("gateway_settings")
async def test_advertised_url_still_honours_gateway(project_id):
    """The client-facing URL keeps the override; only the composer upstream is local."""
    url = await get_project_streamable_http_url(project_id)

    assert url == f"https://gw.example.com/api/v1/mcp/project/{project_id}/streamable"
