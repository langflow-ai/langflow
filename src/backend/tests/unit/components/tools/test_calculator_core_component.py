import pytest
from langflow.components.tools import CalculatorComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCalculatorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CalculatorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"expression": "4*4*(33/22)+12-20"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_evaluate_expression_valid(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.evaluate_expression()
        assert result.data["result"] == "4.0"

    def test_evaluate_expression_division_by_zero(self, component_class):
        component = component_class(expression="1/0")
        result = component.evaluate_expression()
        assert result.data["error"] == "Error: Division by zero"

    def test_evaluate_expression_invalid_syntax(self, component_class):
        component = component_class(expression="4*+4")
        result = component.evaluate_expression()
        assert "Invalid expression" in result.data["error"]

    def test_evaluate_expression_unsupported_operator(self, component_class):
        component = component_class(expression="4 ** 2")
        result = component.evaluate_expression()
        assert result.data["result"] == "16.0"

    def test_evaluate_expression_with_float(self, component_class):
        component = component_class(expression="4.5 * 2")
        result = component.evaluate_expression()
        assert result.data["result"] == "9.0"
