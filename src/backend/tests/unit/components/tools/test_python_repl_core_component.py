import pytest

from langflow.components.tools import PythonREPLComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPythonREPLComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PythonREPLComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"global_imports": "math,pandas", "python_code": "print('Hello, World!')", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_get_globals_with_string_imports(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        globals_dict = component.get_globals(default_kwargs["global_imports"])
        assert "math" in globals_dict
        assert "pandas" in globals_dict

    def test_get_globals_with_list_imports(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        globals_dict = component.get_globals(["math", "pandas"])
        assert "math" in globals_dict
        assert "pandas" in globals_dict

    def test_run_python_repl_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_python_repl()
        assert result.data["result"] == "Hello, World!"

    def test_run_python_repl_import_error(self, component_class):
        component = component_class(global_imports="non_existent_module", python_code="print('Hello')")
        result = component.run_python_repl()
        assert "Import Error" in result.data["error"]

    def test_run_python_repl_syntax_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.python_code = "print('Hello'"
        result = component.run_python_repl()
        assert "Syntax Error" in result.data["error"]

    def test_run_python_repl_execution_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.python_code = "undefined_function()"
        result = component.run_python_repl()
        assert "Error during execution" in result.data["error"]
