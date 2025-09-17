import pytest

from lfx.components.processing import PythonREPLComponent
from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient


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
        # Component not yet released, mark all versions as non-existent
        return [
            {"version": "1.0.17", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.0.18", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.0.19", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "tools", "file_name": DID_NOT_EXIST},
        ]

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
