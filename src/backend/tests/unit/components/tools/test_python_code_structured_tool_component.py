import pytest

from langflow.components.tools import PythonCodeStructuredTool
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPythonCodeStructuredTool(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PythonCodeStructuredTool

    @pytest.fixture
    def default_kwargs(self):
        return {
            "tool_code": "def my_function(x): return x * 2",
            "tool_name": "My Function",
            "tool_description": "A function that doubles the input.",
            "return_direct": True,
            "tool_function": "my_function",
            "global_variables": [],
            "_classes": "",
            "_functions": "",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tools", "file_name": "PythonCodeStructuredTool"},
        ]

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = await component.build_tool()
        assert tool is not None
        assert tool.name == "My Function"
        assert tool.description == "A function that doubles the input."
        assert callable(tool.func)

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "tool_code": {"value": "def my_function(x): return x * 2"},
            "tool_function": {"options": []},
            "_functions": {"value": ""},
            "_classes": {"value": ""},
        }
        updated_config = await component.update_build_config(
            build_config, build_config["tool_code"]["value"], "tool_code"
        )
        assert "my_function" in updated_config["tool_function"]["options"]
        assert updated_config["_functions"]["value"] != ""
        assert updated_config["_classes"]["value"] == ""

    async def test_update_frontend_node(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        new_frontend_node = {
            "template": {
                "tool_code": {"value": "def new_function(x): return x + 1"},
                "tool_name": {"value": "New Function"},
                "tool_description": {"value": "A function that adds one."},
            }
        }
        current_frontend_node = {
            "template": {
                "tool_code": {"value": "def my_function(x): return x * 2"},
                "tool_name": {"value": "My Function"},
                "tool_description": {"value": "A function that doubles the input."},
            }
        }
        updated_node = await component.update_frontend_node(new_frontend_node, current_frontend_node)
        assert updated_node["template"]["tool_code"]["value"] == "def new_function(x): return x + 1"
        assert updated_node["template"]["tool_name"]["value"] == "New Function"
        assert updated_node["template"]["tool_description"]["value"] == "A function that adds one."
