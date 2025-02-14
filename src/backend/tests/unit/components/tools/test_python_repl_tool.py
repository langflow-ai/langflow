import pytest
from langflow.components.tools import PythonREPLComponent

from tests.base import ComponentTestBaseWithoutClient


class TestPythonREPLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return PythonREPLComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "global_imports": "math",
            "python_code": "print('Hello, World!')",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def module(self):
        """Return the module name for the component."""
        return "tools"

    @pytest.fixture
    def file_name(self):
        """Return the file name for the component."""
        return "python_repl"

    def test_component_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        # Test template fields
        template = node_data["template"]
        assert "global_imports" in template
        assert "python_code" in template

        # Test global_imports configuration
        global_imports = template["global_imports"]
        assert global_imports["type"] == "str"
        assert global_imports["value"] == "math"
        assert global_imports["required"] is True

        # Test python_code configuration
        python_code = template["python_code"]
        assert python_code["type"] == "code"
        assert python_code["value"] == "print('Hello, World!')"
        assert python_code["required"] is True

        # Test base configuration
        assert "Data" in node_data["base_classes"]
