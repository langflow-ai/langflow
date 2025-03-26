import pytest
from langflow.components.tools.mcp_sse import MCPSse

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMCPSseComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MCPSse

    @pytest.fixture
    def default_kwargs(self):
        return {"url": "http://localhost:7860/api/v1/mcp/sse"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tools", "file_name": "MCPSse"},
            {"version": "1.1.0", "module": "tools", "file_name": "mcps_sse"},
        ]

    async def test_build_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_output()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(tool, dict) for tool in result)

    async def test_connect_to_server(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tools = await component.build_output()
        assert len(tools) > 0
        assert all("name" in tool for tool in tools)
        assert all("description" in tool for tool in tools)

    async def test_pre_check_redirect(self, component_class):
        client = component_class.client
        redirect_url = await client.pre_check_redirect("http://example.com/redirect")
        assert redirect_url is not None
