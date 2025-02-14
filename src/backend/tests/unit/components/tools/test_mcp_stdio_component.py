import pytest

from langflow.components.tools import MCPStdio
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMCPStdioComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MCPStdio

    @pytest.fixture
    def default_kwargs(self):
        return {"command": "uvx mcp-sse-shim@latest"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_output()
        assert result is not None
        assert isinstance(result, list)
        assert all(isinstance(tool, dict) for tool in result), "All tools should be dictionaries."

    async def test_connect_to_server(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.client.connect_to_server(default_kwargs["command"])
        assert component.client.session is not None, "Session should be initialized after connecting to server."
