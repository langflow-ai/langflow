import pytest

from langflow.components.tools import PythonREPLToolComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPythonREPLToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PythonREPLToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "name": "python_repl",
            "description": "A Python shell.",
            "global_imports": "math",
            "code": "print('Hello, World!')",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == default_kwargs["name"]
        assert tool.description == default_kwargs["description"]

    def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert "result" in result[0].data
        assert result[0].data["result"] == "Hello, World!\n"  # Output includes newline from print
