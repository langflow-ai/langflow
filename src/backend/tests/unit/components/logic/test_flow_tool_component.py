import pytest

from langflow.components.logic import FlowToolComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestFlowToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return FlowToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "flow_name": "example_flow",
            "tool_name": "Example Tool",
            "tool_description": "This is an example tool.",
            "return_direct": True,
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tools", "file_name": "FlowTool"},
            {"version": "1.1.0", "module": "tools", "file_name": "flow_tool"},
        ]

    async def test_build_tool_with_valid_flow(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = await component.build_tool()
        assert tool is not None
        assert tool.name == default_kwargs["tool_name"]
        assert tool.description == default_kwargs["tool_description"]

    async def test_build_tool_without_flow_name(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "flow_name": ""})
        with pytest.raises(ValueError, match="Flow name is required"):
            await component.build_tool()

    async def test_build_tool_with_nonexistent_flow(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "flow_name": "nonexistent_flow"})
        with pytest.raises(ValueError, match="Flow not found."):
            await component.build_tool()

    async def test_get_flow_names(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow_names = await component.get_flow_names()
        assert isinstance(flow_names, list)
        assert len(flow_names) > 0  # Assuming there are flows available

    async def test_get_flow_with_existing_name(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow_data = await component.get_flow("example_flow")
        assert flow_data is not None
        assert flow_data.data["name"] == "example_flow"

    async def test_get_flow_with_nonexistent_name(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        flow_data = await component.get_flow("nonexistent_flow")
        assert flow_data is None
