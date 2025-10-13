from lfx.components.processing import DynamicCreateDataComponent
from lfx.schema.data import Data
from lfx.schema.message import Message


class TestDynamicCreateDataComponent:
    def test_update_build_config_creates_dynamic_inputs(self):
        """Test that dynamic inputs are created based on form_fields configuration."""
        component = DynamicCreateDataComponent()
        build_config = {"form_fields": {"value": []}}

        field_value = [
            {"field_name": "username", "field_type": "Text"},
            {"field_name": "age", "field_type": "Number"},
            {"field_name": "active", "field_type": "Boolean"},
        ]

        result = component.update_build_config(build_config, field_value, "form_fields")

        assert "dynamic_username" in result
        assert "dynamic_age" in result
        assert "dynamic_active" in result
        assert result["dynamic_username"].display_name == "username"
        assert result["dynamic_age"].display_name == "age"

    def test_update_build_config_clears_old_dynamic_inputs(self):
        """Test that old dynamic inputs are removed when form_fields change."""
        component = DynamicCreateDataComponent()
        build_config = {
            "dynamic_old_field": {"display_name": "Old Field"},
            "form_fields": {"value": []},
        }

        field_value = [{"field_name": "new_field", "field_type": "Text"}]

        result = component.update_build_config(build_config, field_value, "form_fields")

        assert "dynamic_old_field" not in result
        assert "dynamic_new_field" in result

    def test_process_form_returns_data_with_simple_values(self):
        """Test that process_form extracts and returns simple values from inputs."""
        component = DynamicCreateDataComponent()
        component.form_fields = [
            {"field_name": "name", "field_type": "Text"},
            {"field_name": "count", "field_type": "Number"},
        ]

        # Simulate manual input values
        component.dynamic_name = "John Doe"
        component.dynamic_count = 42

        result = component.process_form()

        assert isinstance(result, Data)
        assert result.data["name"] == "John Doe"
        assert result.data["count"] == 42

    def test_extract_simple_value_handles_message_objects(self):
        """Test that Message objects are properly extracted to their text content."""
        component = DynamicCreateDataComponent()

        test_message = Message(text="Hello World")
        result = component._extract_simple_value(test_message)

        assert result == "Hello World"
        assert isinstance(result, str)

    def test_get_message_formats_data_as_text(self):
        """Test that get_message returns properly formatted text output."""
        component = DynamicCreateDataComponent()
        component.form_fields = [
            {"field_name": "title", "field_type": "Text"},
            {"field_name": "enabled", "field_type": "Boolean"},
        ]

        component.dynamic_title = "Test Title"
        component.dynamic_enabled = True

        result = component.get_message()

        assert isinstance(result, Message)
        assert "title" in result.text
        assert "Test Title" in result.text
        assert "enabled" in result.text

    def test_handles_none_field_config_gracefully(self):
        """Test that None values in form_fields are handled without errors."""
        component = DynamicCreateDataComponent()
        build_config = {"form_fields": {"value": []}}

        field_value = [
            {"field_name": "valid_field", "field_type": "Text"},
            None,  # This should be skipped
            {"field_name": "another_field", "field_type": "Number"},
        ]

        result = component.update_build_config(build_config, field_value, "form_fields")

        assert "dynamic_valid_field" in result
        assert "dynamic_another_field" in result
