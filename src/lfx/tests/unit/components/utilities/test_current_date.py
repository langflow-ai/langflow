"""Tests for CurrentDateComponent tool schema optimization."""

import json

from lfx.base.tools.component_tool import ComponentToolkit
from lfx.components.utilities.current_date import CurrentDateComponent
from lfx.io.schema import MAX_OPTIONS_FOR_TOOL_ENUM


class TestCurrentDateToolSchema:
    """Tests to verify tool schema doesn't waste tokens on large option lists."""

    def test_should_not_include_enum_when_options_exceed_limit(self):
        """Verify schema uses string type instead of enum for large option lists."""
        # Arrange
        component = CurrentDateComponent()
        # Populate options via update_build_config
        build_config = {"timezone": {"options": []}}
        component.update_build_config(build_config, "", "timezone")
        component.inputs[0].options = build_config["timezone"]["options"]
        toolkit = ComponentToolkit(component)

        # Act
        tools = toolkit.get_tools()
        tool = tools[0]
        schema = tool.args_schema.model_json_schema()

        # Assert
        assert len(component.inputs[0].options) > MAX_OPTIONS_FOR_TOOL_ENUM
        assert "enum" not in json.dumps(schema)
        assert schema["properties"]["timezone"]["type"] == "string"

    def test_should_have_default_value_in_schema(self):
        """Verify schema includes default value when enum is skipped."""
        # Arrange
        component = CurrentDateComponent()
        toolkit = ComponentToolkit(component)

        # Act
        tools = toolkit.get_tools()
        schema = tools[0].args_schema.model_json_schema()

        # Assert
        assert schema["properties"]["timezone"]["default"] == "UTC"

    def test_should_reduce_schema_size_significantly(self):
        """Verify schema size is reasonable (not wasting tokens)."""
        # Arrange
        component = CurrentDateComponent()
        toolkit = ComponentToolkit(component)
        max_acceptable_chars = 500  # Before fix was ~16000

        # Act
        tools = toolkit.get_tools()
        schema_str = json.dumps(tools[0].args_schema.model_json_schema())

        # Assert
        assert len(schema_str) < max_acceptable_chars


class TestCurrentDateFunctionality:
    """Tests to verify component still works correctly."""

    def test_should_return_utc_time_by_default(self):
        """Verify component returns UTC time when using default timezone."""
        # Arrange
        component = CurrentDateComponent()

        # Act
        result = component.get_current_date()

        # Assert
        assert "UTC" in result.text

    def test_should_return_time_in_specified_timezone(self):
        """Verify component respects timezone selection."""
        # Arrange
        component = CurrentDateComponent()
        component.timezone = "America/New_York"

        # Act
        result = component.get_current_date()

        # Assert
        assert "America/New_York" in result.text or "EST" in result.text or "EDT" in result.text

    def test_should_handle_invalid_timezone_gracefully(self):
        """Verify component returns error for invalid timezone."""
        # Arrange
        component = CurrentDateComponent()
        component.timezone = "Invalid/Timezone"

        # Act
        result = component.get_current_date()

        # Assert
        assert "Error" in result.text
