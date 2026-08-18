"""Unit tests for ``WatsonxDataMCPComponent`` (``lfx-ibm``).

The MCP engine (``lfx.base.mcp.util.update_tools``) and the IAM token
exchange are patched, so the tests cover endpoint templating, both auth
modes, Tool-Mode wiring, and the dropdown toggles without network access.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_ibm import WatsonxDataMCPComponent
from lfx_ibm.components.ibm.watsonx_data_mcp import (
    WATSONX_DATA_MCP_TOOLS,
    iam_bearer_token,
    watsonx_data_mcp_url,
)

UPDATE_TOOLS_TARGET = "lfx.base.mcp.preset.update_tools"
IAM_TARGET = "lfx_ibm.components.ibm.watsonx_data_mcp.iam_bearer_token"


def _tool(name: str):
    async def coroutine(**_kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"ok": true}')])

    return SimpleNamespace(name=name, description=name, coroutine=coroutine)


@pytest.fixture
def component() -> WatsonxDataMCPComponent:
    c = WatsonxDataMCPComponent()
    c.instance_url = "https://my-instance.lakehouse.cloud.ibm.com"
    c.auth_mode = "bearer_token"
    c.bearer_token = "tok"  # noqa: S105  # pragma: allowlist secret
    c.api_key = ""
    c.iam_url = "https://iam.cloud.ibm.com"
    c.endpoint_override = ""
    c.tool = ""
    c.tool_arguments = "{}"
    c.tool_execution_timeout = 0.0
    c.verify_ssl = True
    return c


def test_component_metadata():
    assert WatsonxDataMCPComponent.__name__ == "WatsonxDataMCPComponent"
    assert WatsonxDataMCPComponent.name == "WatsonxDataMCP"
    assert WatsonxDataMCPComponent.add_tool_output is True


def test_tool_dropdown_seeded_with_documented_tools():
    tool_input = next(i for i in WatsonxDataMCPComponent.inputs if i.name == "tool")
    assert tool_input.options == WATSONX_DATA_MCP_TOOLS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://host.example.com", "https://host.example.com/api/v2/mcp/"),
        ("https://host.example.com/", "https://host.example.com/api/v2/mcp/"),
        ("host.example.com", "https://host.example.com/api/v2/mcp/"),
        ("https://host.example.com/api/v2/mcp", "https://host.example.com/api/v2/mcp/"),
        ("https://host.example.com/api/v2/mcp/", "https://host.example.com/api/v2/mcp/"),
    ],
)
def test_watsonx_data_mcp_url(raw, expected):
    assert watsonx_data_mcp_url(raw) == expected


def test_watsonx_data_mcp_url_requires_value():
    with pytest.raises(ValueError, match="instance URL is required"):
        watsonx_data_mcp_url("  ")


@pytest.mark.parametrize("raw", ["http://host.example.com", "http://host.example.com/api/v2/mcp/"])
def test_watsonx_data_mcp_url_rejects_plaintext_http(raw):
    """A public HTTP host passes SSRF validation but would carry the bearer token in clear."""
    with pytest.raises(ValueError, match="must use https"):
        watsonx_data_mcp_url(raw)


def test_endpoint_override_rejects_plaintext_http(component):
    component.endpoint_override = "http://host.example.com/api/v2/mcp/"
    with pytest.raises(ValueError, match="must use https"):
        component.endpoint_url()


def test_iam_bearer_token_rejects_plaintext_iam_url():
    """The IAM exchange posts the IBM Cloud API key; a public HTTP IAM URL must be refused."""
    with pytest.raises(ValueError, match="must use https"):
        iam_bearer_token("iam-key", "http://iam.example.com")


def test_endpoint_url_and_override_are_ssrf_checked(component):
    assert component.endpoint_url() == "https://my-instance.lakehouse.cloud.ibm.com/api/v2/mcp/"
    component.endpoint_override = "https://other.example.com/api/v2/mcp/"
    assert component.endpoint_url() == "https://other.example.com/api/v2/mcp/"
    component.endpoint_override = "https://10.0.0.5/api/v2/mcp/"
    with pytest.raises(SSRFProtectionError):
        component.endpoint_url()


async def test_mcp_server_config_bearer_mode(component):
    name, config = await component._mcp_server_config()
    assert name == "watsonx-data-mcp"
    assert config["url"] == "https://my-instance.lakehouse.cloud.ibm.com/api/v2/mcp/"
    assert config["headers"] == {"Authorization": "Bearer tok"}
    assert config["mode"] == "Streamable_HTTP"


async def test_mcp_server_config_iam_mode_exchanges_api_key(component):
    component.auth_mode = "ibm_iam_apikey"
    component.api_key = "iam-key"  # pragma: allowlist secret
    with patch(IAM_TARGET, return_value="exchanged") as iam:
        _, config = await component._mcp_server_config()
    iam.assert_called_once_with("iam-key", "https://iam.cloud.ibm.com")
    assert config["headers"] == {"Authorization": "Bearer exchanged"}


async def test_bearer_mode_requires_token(component):
    component.bearer_token = ""
    with pytest.raises(ValueError, match="Bearer Token is required"):
        await component._mcp_server_config()


async def test_update_build_config_toggles_auth_fields(component):
    build_config = {"api_key": {"show": False}, "bearer_token": {"show": True}}
    out = await component.update_build_config(dict(build_config), "ibm_iam_apikey", field_name="auth_mode")
    assert out["api_key"]["show"] is True
    assert out["bearer_token"]["show"] is False
    out = await component.update_build_config(dict(build_config), "bearer_token", field_name="auth_mode")
    assert out["api_key"]["show"] is False
    assert out["bearer_token"]["show"] is True


async def test_get_tools_passes_bearer_header_to_engine(component):
    tools = [_tool("LIST_DOCUMENT_LIBRARY"), _tool("QUERY_DATA_ASSETS")]
    engine = AsyncMock(return_value=("Streamable_HTTP", tools, {t.name: t for t in tools}))
    with patch(UPDATE_TOOLS_TARGET, new=engine) as upd:
        got = await component._get_tools()
    assert [t.name for t in got] == ["LIST_DOCUMENT_LIBRARY", "QUERY_DATA_ASSETS"]
    _, server_config = upd.await_args.args[:2]
    assert server_config["headers"]["Authorization"] == "Bearer tok"


async def test_run_tool_direct_output(component):
    tools = [_tool("LIST_DOCUMENT_LIBRARY")]
    component.tool = "LIST_DOCUMENT_LIBRARY"
    with patch(UPDATE_TOOLS_TARGET, new=AsyncMock(return_value=("Streamable_HTTP", tools, {t.name: t for t in tools}))):
        frame = await component.run_tool()
    assert frame.to_dict(orient="records") == [{"ok": True}]
