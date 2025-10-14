from unittest.mock import patch

import pytest
from langflow.components.logic.data_conditional_router import DataConditionalRouterComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestDataConditionalRouterComponent(ComponentTestBaseWithoutClient):
    """Test cases for DataConditionalRouterComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return DataConditionalRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data_input": None,
            "key_name": "test_key",
            "operator": "equals",
            "compare_value": "test_value",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_component_initialization(self, component_class, default_kwargs):
        """Test proper initialization of DataConditionalRouterComponent."""
        component = await self.component_setup(component_class, default_kwargs)
        assert component.display_name == "Condition"
        assert "Route Data object" in component.description
        assert component.name == "DataConditionalRouter"
        assert component.icon == "split"
        assert component.legacy is True

    async def test_inputs_configuration(self, component_class, default_kwargs):
        """Test that inputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        assert len(component.inputs) == 4

        input_names = [inp.name for inp in component.inputs]
        expected_inputs = ["data_input", "key_name", "operator", "compare_value"]
        for expected_input in expected_inputs:
            assert expected_input in input_names

        # Test data_input configuration
        data_input = next(inp for inp in component.inputs if inp.name == "data_input")
        assert data_input.is_list is True

    async def test_outputs_configuration(self, component_class, default_kwargs):
        """Test that outputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        assert len(component.outputs) == 2
        output_names = [out.name for out in component.outputs]
        assert "true_output" in output_names
        assert "false_output" in output_names

    @pytest.mark.parametrize(
        ("item_value", "compare_value", "operator", "expected"),
        [
            # Equals tests
            ("hello", "hello", "equals", True),
            ("hello", "world", "equals", False),
            # Not equals tests
            ("hello", "world", "not equals", True),
            ("hello", "hello", "not equals", False),
            # Contains tests
            ("hello world", "world", "contains", True),
            ("hello world", "foo", "contains", False),
            # Starts with tests
            ("hello world", "hello", "starts with", True),
            ("hello world", "world", "starts with", False),
            # Ends with tests
            ("hello world", "world", "ends with", True),
            ("hello world", "hello", "ends with", False),
        ],
    )
    async def test_compare_values(self, component_class, default_kwargs, item_value, compare_value, operator, expected):
        """Test compare_values method with various operators."""
        component = await self.component_setup(component_class, default_kwargs)
        result = component.compare_values(item_value, compare_value, operator)
        assert result == expected

    async def test_compare_values_boolean_validator(self, component_class, default_kwargs):
        """Test compare_values with boolean validator."""
        component = await self.component_setup(component_class, default_kwargs)
        result = component.compare_values("true", "", "boolean validator")
        assert result is True

        result = component.compare_values("false", "", "boolean validator")
        assert result is False

    async def test_compare_values_unknown_operator(self, component_class, default_kwargs):
        """Test compare_values with unknown operator."""
        component = await self.component_setup(component_class, default_kwargs)
        result = component.compare_values("hello", "hello", "unknown_operator")
        assert result is False

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            # Boolean values
            (True, True),
            (False, False),
            # String values
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("y", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
            # Other values
            (1, True),
            (0, False),
            ([], False),
            ([1], True),
            ("", False),
            ("hello", False),
        ],
    )
    async def test_parse_boolean(self, component_class, default_kwargs, value, expected):
        """Test parse_boolean method with various input types."""
        component = await self.component_setup(component_class, default_kwargs)
        result = component.parse_boolean(value)
        assert result == expected

    async def test_validate_input_valid_data(self, component_class, default_kwargs):
        """Test validate_input with valid Data object."""
        component = await self.component_setup(component_class, default_kwargs)
        component.key_name = "test_key"
        data_item = Data(data={"test_key": "value"})

        result = component.validate_input(data_item)
        assert result is True

    async def test_validate_input_invalid_type(self, component_class, default_kwargs):
        """Test validate_input with non-Data object."""
        component = await self.component_setup(component_class, default_kwargs)
        component.key_name = "test_key"

        result = component.validate_input("not_data")
        assert result is False
        assert component.status == "Input is not a Data object"

    async def test_validate_input_missing_key(self, component_class, default_kwargs):
        """Test validate_input with missing key in Data object."""
        component = await self.component_setup(component_class, default_kwargs)
        component.key_name = "missing_key"
        data_item = Data(data={"other_key": "value"})

        result = component.validate_input(data_item)
        assert result is False
        assert component.status == "Key 'missing_key' not found in Data"

    async def test_process_single_data_boolean_validator(self, component_class, default_kwargs):
        """Test process_single_data with boolean validator."""
        component = await self.component_setup(component_class, default_kwargs)
        component.operator = "boolean validator"
        component.key_name = "flag"
        data_item = Data(data={"flag": True})

        result = component.process_single_data(data_item)
        assert result is True
        assert "Boolean validation of 'flag'" in component.status

    async def test_process_single_data_comparison_true(self, component_class, default_kwargs):
        """Test process_single_data with comparison that returns True."""
        component = await self.component_setup(component_class, default_kwargs)
        component.operator = "equals"
        component.key_name = "name"
        component.compare_value = "test"
        data_item = Data(data={"name": "test"})

        result = component.process_single_data(data_item)
        assert result is True
        assert "Condition met: name equals test" in component.status

    async def test_process_single_data_comparison_false(self, component_class, default_kwargs):
        """Test process_single_data with comparison that returns False."""
        component = await self.component_setup(component_class, default_kwargs)
        component.operator = "equals"
        component.key_name = "name"
        component.compare_value = "test"
        data_item = Data(data={"name": "other"})

        result = component.process_single_data(data_item)
        assert result is False
        assert "Condition not met: name equals test" in component.status

    async def test_process_data_single_valid_input_true(self, component_class, default_kwargs):
        """Test process_data with single valid input that evaluates to True."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = Data(data={"key": "value"})
        component.key_name = "key"
        component.operator = "equals"
        component.compare_value = "value"

        with patch.object(component, "stop") as mock_stop:
            result = component.process_data()

            assert result == component.data_input
            mock_stop.assert_called_once_with("false_output")

    async def test_process_data_single_valid_input_false(self, component_class, default_kwargs):
        """Test process_data with single valid input that evaluates to False."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = Data(data={"key": "value"})
        component.key_name = "key"
        component.operator = "equals"
        component.compare_value = "other"

        with patch.object(component, "stop") as mock_stop:
            result = component.process_data()

            assert result == component.data_input
            mock_stop.assert_called_once_with("true_output")

    async def test_process_data_single_invalid_input(self, component_class, default_kwargs):
        """Test process_data with single invalid input."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = Data(data={"other_key": "value"})
        component.key_name = "key"

        result = component.process_data()

        assert isinstance(result, Data)
        assert result.data["error"] == "Key 'key' not found in Data"

    async def test_process_data_list_input_mixed_results(self, component_class, default_kwargs):
        """Test process_data with list input containing mixed results."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = [
            Data(data={"key": "match"}),
            Data(data={"key": "no_match"}),
            Data(data={"key": "match"}),
        ]
        component.key_name = "key"
        component.operator = "equals"
        component.compare_value = "match"

        with patch.object(component, "stop") as mock_stop:
            result = component.process_data()

            # Should return true_output (items that match)
            assert len(result) == 2
            assert all(item.data["key"] == "match" for item in result)
            mock_stop.assert_called_once_with("false_output")

    async def test_process_data_list_input_no_matches(self, component_class, default_kwargs):
        """Test process_data with list input containing no matches."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = [
            Data(data={"key": "no_match1"}),
            Data(data={"key": "no_match2"}),
        ]
        component.key_name = "key"
        component.operator = "equals"
        component.compare_value = "match"

        with patch.object(component, "stop") as mock_stop:
            result = component.process_data()

            # Should return false_output (items that don't match)
            assert len(result) == 2
            mock_stop.assert_called_once_with("true_output")

    async def test_process_data_list_input_invalid_items(self, component_class, default_kwargs):
        """Test process_data with list input containing invalid items."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = [
            Data(data={"other_key": "value"}),  # Invalid - missing key
            Data(data={"key": "match"}),  # Valid
        ]
        component.key_name = "key"
        component.operator = "equals"
        component.compare_value = "match"

        with patch.object(component, "stop") as mock_stop:
            result = component.process_data()

            # Should only return the valid matching item
            assert len(result) == 1
            assert result[0].data["key"] == "match"
            mock_stop.assert_called_once_with("false_output")

    async def test_update_build_config_boolean_validator(self, component_class, default_kwargs):
        """Test update_build_config when operator is boolean validator."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"compare_value": {"show": True, "advanced": False, "value": "test"}}

        result = component.update_build_config(build_config, "boolean validator", "operator")

        assert result["compare_value"]["show"] is False
        assert result["compare_value"]["advanced"] is True
        assert result["compare_value"]["value"] is None

    async def test_update_build_config_non_boolean_validator(self, component_class, default_kwargs):
        """Test update_build_config when operator is not boolean validator."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"compare_value": {"show": False, "advanced": True}}

        result = component.update_build_config(build_config, "equals", "operator")

        assert result["compare_value"]["show"] is True
        assert result["compare_value"]["advanced"] is False

    async def test_update_build_config_non_operator_field(self, component_class, default_kwargs):
        """Test update_build_config when field is not operator."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"some_field": "value"}

        result = component.update_build_config(build_config, "some_value", "some_field")

        assert result == build_config  # Should return unchanged

    async def test_process_data_empty_list(self, component_class, default_kwargs):
        """Test process_data with empty list input."""
        component = await self.component_setup(component_class, default_kwargs)
        component.data_input = []
        component.key_name = "key"
        component.operator = "equals"
        component.compare_value = "value"

        with patch.object(component, "stop") as mock_stop:
            result = component.process_data()

            assert result == []
            mock_stop.assert_called_once_with("true_output")

    async def test_numeric_value_handling(self, component_class, default_kwargs):
        """Test that numeric values are properly converted to strings for comparison."""
        component = await self.component_setup(component_class, default_kwargs)
        component.operator = "equals"
        component.key_name = "number"
        component.compare_value = "42"
        data_item = Data(data={"number": 42})

        result = component.process_single_data(data_item)
        assert result is True

    async def test_none_value_handling(self, component_class, default_kwargs):
        """Test handling of None values in data."""
        component = await self.component_setup(component_class, default_kwargs)
        component.operator = "boolean validator"
        component.key_name = "nullable"
        data_item = Data(data={"nullable": None})

        result = component.process_single_data(data_item)
        assert result is False  # None should be falsy
