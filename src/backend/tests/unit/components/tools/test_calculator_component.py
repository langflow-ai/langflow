import pytest

from langflow.components.tools import CalculatorToolComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCalculatorToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CalculatorToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"expression": "4*4*(33/22)+12-20"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "calculator", "file_name": "CalculatorTool"},
        ]

    def test_evaluate_expression(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.run_model()
        assert result is not None
        assert "result" in result[0].data
        assert result[0].data["result"] == "8.0"

    def test_invalid_expression(self, component_class):
        component = component_class(expression="4/0")
        result = component.run_model()
        assert result is not None
        assert "error" in result[0].data
        assert result[0].data["error"] == "Error: Division by zero"

    def test_syntax_error_expression(self, component_class):
        component = component_class(expression="4*+4")
        result = component.run_model()
        assert result is not None
        assert "error" in result[0].data
        assert "Invalid expression" in result[0].data["error"]

    def test_unsupported_operation(self, component_class):
        component = component_class(expression="sqrt(4)")
        result = component.run_model()
        assert result is not None
        assert "error" in result[0].data
        assert "Function calls like sqrt()" in result[0].data["error"]

    def test_valid_expression_with_decimal(self, component_class):
        component = component_class(expression="5/2")
        result = component.run_model()
        assert result is not None
        assert "result" in result[0].data
        assert result[0].data["result"] == "2.5"
