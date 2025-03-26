import pytest
from langflow.components.prototypes import PythonFunctionComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPythonFunctionComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PythonFunctionComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"function_code": "def test_func(): return 'Hello, World!'"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "python_function", "file_name": "PythonFunction"},
        ]

    def test_get_function_callable(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        function_callable = component.get_function_callable()
        assert callable(function_callable), "The callable should be a function."

    def test_execute_function_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.execute_function_data()
        assert isinstance(result, list), "The result should be a list."
        assert len(result) == 1, "The result list should contain one item."
        assert result[0].text == "Hello, World!", "The output should match the expected string."

    def test_execute_function_message(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.execute_function_message()
        assert result.text == "Hello, World!", "The message output should match the expected string."

    def test_execute_function_with_error(self, component_class):
        component = component_class(function_code="def faulty_func(): raise ValueError('Error')")
        result = component.execute_function()
        assert "Error executing function: Error" in result, "The error message should be returned."
