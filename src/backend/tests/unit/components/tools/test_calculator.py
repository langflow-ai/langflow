import pytest
from langflow.components.helpers.calculator_core import CalculatorComponent

from tests.base import ComponentTestBaseWithoutClient


class TestCalculatorComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return CalculatorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"expression": "2 + 2", "_session_id": "test_session"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_basic_calculation(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.evaluate_expression()

        # Assert
        assert result.data["result"] == "4"

    def test_complex_calculation(self, component_class):
        # Arrange
        component = component_class(expression="4*4*(33/22)+12-20", _session_id="test_session")

        # Act
        result = component.evaluate_expression()

        # Assert
        assert float(result.data["result"]) == pytest.approx(16)

    def test_division_by_zero(self, component_class):
        # Arrange
        component = component_class(expression="1/0", _session_id="test_session")

        # Act
        result = component.evaluate_expression()

        # Assert
        assert "error" in result.data
        assert result.data["error"] == "Error: Division by zero"

    def test_invalid_expression(self, component_class):
        # Arrange
        component = component_class(expression="2 + *", _session_id="test_session")

        # Act
        result = component.evaluate_expression()

        # Assert
        assert "error" in result.data
        assert "Invalid expression" in result.data["error"]

    def test_unsupported_operation(self, component_class):
        # Arrange
        component = component_class(expression="sqrt(16)", _session_id="test_session")

        # Act
        result = component.evaluate_expression()

        # Assert
        assert "error" in result.data
        assert "Unsupported operation" in result.data["error"]

    def test_component_frontend_node(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        frontend_node = component.to_frontend_node()

        # Assert
        node_data = frontend_node["data"]["node"]
        assert node_data["display_name"] == "Calculator"
        assert node_data["description"] == "Perform basic arithmetic operations on a given expression."
        assert node_data["icon"] == "calculator"
