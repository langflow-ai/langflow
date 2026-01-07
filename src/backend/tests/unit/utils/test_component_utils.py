from unittest.mock import Mock

from langflow.schema.dotdict import dotdict
from langflow.utils.component_utils import (
    DEFAULT_FIELDS,
    add_fields,
    delete_fields,
    get_fields,
    merge_build_configs,
    set_current_fields,
    set_field_advanced,
    set_field_display,
    set_multiple_field_advanced,
    set_multiple_field_display,
    update_fields,
    update_input_types,
)


class TestUpdateFields:
    """Test cases for update_fields function."""

    def test_update_existing_fields(self):
        """Test updating existing fields in build_config."""
        build_config = dotdict({"field1": "old_value", "field2": "old_value2"})
        fields = {"field1": "new_value", "field2": "new_value2"}

        result = update_fields(build_config, fields)

        assert result["field1"] == "new_value"
        assert result["field2"] == "new_value2"

    def test_update_non_existing_fields_ignored(self):
        """Test that non-existing fields are ignored."""
        build_config = dotdict({"field1": "value1"})
        fields = {"field1": "new_value", "non_existing": "ignored"}

        result = update_fields(build_config, fields)

        assert result["field1"] == "new_value"
        assert "non_existing" not in result

    def test_update_empty_fields(self):
        """Test updating with empty fields dict."""
        build_config = dotdict({"field1": "value1"})
        fields = {}

        result = update_fields(build_config, fields)

        assert result["field1"] == "value1"

    def test_update_fields_returns_same_object(self):
        """Test that update_fields modifies and returns the same object."""
        build_config = dotdict({"field1": "value1"})
        fields = {"field1": "new_value"}

        result = update_fields(build_config, fields)

        assert result is build_config
        assert build_config["field1"] == "new_value"


class TestAddFields:
    """Test cases for add_fields function."""

    def test_add_new_fields(self):
        """Test adding new fields to build_config."""
        build_config = dotdict({"existing": "value"})
        fields = {"new_field1": "value1", "new_field2": "value2"}

        result = add_fields(build_config, fields)

        assert result["existing"] == "value"
        assert result["new_field1"] == "value1"
        assert result["new_field2"] == "value2"

    def test_add_fields_overwrites_existing(self):
        """Test that add_fields overwrites existing fields."""
        build_config = dotdict({"field1": "old_value"})
        fields = {"field1": "new_value", "field2": "value2"}

        result = add_fields(build_config, fields)

        assert result["field1"] == "new_value"
        assert result["field2"] == "value2"

    def test_add_empty_fields(self):
        """Test adding empty fields dict."""
        build_config = dotdict({"field1": "value1"})
        fields = {}

        result = add_fields(build_config, fields)

        assert result["field1"] == "value1"
        assert len(result) == 1

    def test_add_fields_returns_same_object(self):
        """Test that add_fields modifies and returns the same object."""
        build_config = dotdict({"field1": "value1"})
        fields = {"field2": "value2"}

        result = add_fields(build_config, fields)

        assert result is build_config


class TestDeleteFields:
    """Test cases for delete_fields function."""

    def test_delete_fields_with_dict(self):
        """Test deleting fields using dict parameter."""
        build_config = dotdict({"field1": "value1", "field2": "value2", "field3": "value3"})
        fields = {"field1": "ignored_value", "field2": "also_ignored"}

        result = delete_fields(build_config, fields)

        assert "field1" not in result
        assert "field2" not in result
        assert result["field3"] == "value3"

    def test_delete_fields_with_list(self):
        """Test deleting fields using list parameter."""
        build_config = dotdict({"field1": "value1", "field2": "value2", "field3": "value3"})
        fields = ["field1", "field3"]

        result = delete_fields(build_config, fields)

        assert "field1" not in result
        assert result["field2"] == "value2"
        assert "field3" not in result

    def test_delete_non_existing_fields(self):
        """Test deleting non-existing fields does not raise error."""
        build_config = dotdict({"field1": "value1"})
        fields = ["field1", "non_existing"]

        result = delete_fields(build_config, fields)

        assert "field1" not in result
        assert len(result) == 0

    def test_delete_fields_returns_same_object(self):
        """Test that delete_fields modifies and returns the same object."""
        build_config = dotdict({"field1": "value1", "field2": "value2"})
        fields = ["field1"]

        result = delete_fields(build_config, fields)

        assert result is build_config


class TestGetFields:
    """Test cases for get_fields function."""

    def test_get_specific_fields(self):
        """Test getting specific fields from build_config."""
        build_config = dotdict({"field1": "value1", "field2": "value2", "field3": "value3"})
        fields = ["field1", "field3"]

        result = get_fields(build_config, fields)

        assert result == {"field1": "value1", "field3": "value3"}

    def test_get_all_fields(self):
        """Test getting all fields when fields is None."""
        build_config = dotdict({"field1": "value1", "field2": "value2"})

        result = get_fields(build_config, None)

        assert result == {"field1": "value1", "field2": "value2"}

    def test_get_non_existing_fields(self):
        """Test getting non-existing fields returns empty dict."""
        build_config = dotdict({"field1": "value1"})
        fields = ["non_existing"]

        result = get_fields(build_config, fields)

        assert result == {}

    def test_get_mixed_existing_and_non_existing(self):
        """Test getting mix of existing and non-existing fields."""
        build_config = dotdict({"field1": "value1", "field2": "value2"})
        fields = ["field1", "non_existing", "field2"]

        result = get_fields(build_config, fields)

        assert result == {"field1": "value1", "field2": "value2"}

    def test_get_fields_returns_new_dict(self):
        """Test that get_fields returns a new dict, not modifying original."""
        build_config = dotdict({"field1": "value1"})

        result = get_fields(build_config, ["field1"])
        result["field1"] = "modified"

        assert build_config["field1"] == "value1"  # Original unchanged


class TestUpdateInputTypes:
    """Test cases for update_input_types function."""

    def test_update_input_types_dict_format(self):
        """Test updating input types for dict format fields."""
        build_config = dotdict(
            {
                "field1": {"input_types": None},
                "field2": {"input_types": ["existing"]},
                "field3": {"other_prop": "value"},
            }
        )

        result = update_input_types(build_config)

        assert result["field1"]["input_types"] == []
        assert result["field2"]["input_types"] == ["existing"]  # Unchanged
        # The function adds input_types to all dict fields that don't have it
        assert result["field3"]["input_types"] == []

    def test_update_input_types_object_format(self):
        """Test updating input types for object format fields."""
        mock_obj1 = Mock()
        mock_obj1.input_types = None
        mock_obj2 = Mock()
        mock_obj2.input_types = ["existing"]

        build_config = dotdict({"field1": mock_obj1, "field2": mock_obj2, "field3": "string_value"})

        _ = update_input_types(build_config)

        assert mock_obj1.input_types == []
        assert mock_obj2.input_types == ["existing"]  # Unchanged

    def test_update_input_types_mixed_formats(self):
        """Test updating input types with mixed dict and object formats."""
        mock_obj = Mock()
        mock_obj.input_types = None

        build_config = dotdict(
            {"dict_field": {"input_types": None, "other": "value"}, "obj_field": mock_obj, "string_field": "value"}
        )

        result = update_input_types(build_config)

        assert result["dict_field"]["input_types"] == []
        assert mock_obj.input_types == []

    def test_update_input_types_no_input_types_attr(self):
        """Test updating with objects that don't have input_types attribute."""
        mock_obj = Mock()
        del mock_obj.input_types  # Remove the attribute

        build_config = dotdict({"field1": mock_obj})

        # Should not raise error
        result = update_input_types(build_config)

        assert result is build_config


class TestSetFieldDisplay:
    """Test cases for set_field_display function."""

    def test_set_field_display_existing_field(self):
        """Test setting display for existing field with show property."""
        build_config = dotdict({"field1": {"show": True, "other": "value"}})

        result = set_field_display(build_config, "field1", value=False)

        assert result["field1"]["show"] is False
        assert result["field1"]["other"] == "value"

    def test_set_field_display_non_existing_field(self):
        """Test setting display for non-existing field does nothing."""
        build_config = dotdict({"field1": {"show": True}})

        result = set_field_display(build_config, "non_existing", value=False)

        assert result["field1"]["show"] is True  # Unchanged

    def test_set_field_display_field_without_show(self):
        """Test setting display for field without show property does nothing."""
        build_config = dotdict({"field1": {"other": "value"}})

        result = set_field_display(build_config, "field1", value=False)

        assert "show" not in result["field1"]

    def test_set_field_display_none_value(self):
        """Test setting display with None value."""
        build_config = dotdict({"field1": {"show": True}})

        result = set_field_display(build_config, "field1", None)

        assert result["field1"]["show"] is None


class TestSetMultipleFieldDisplay:
    """Test cases for set_multiple_field_display function."""

    def test_set_multiple_field_display_with_fields_dict(self):
        """Test setting display for multiple fields using fields dict."""
        build_config = dotdict({"field1": {"show": True}, "field2": {"show": True}, "field3": {"show": True}})
        fields = {"field1": False, "field2": True}

        result = set_multiple_field_display(build_config, fields=fields)

        assert result["field1"]["show"] is False
        assert result["field2"]["show"] is True
        assert result["field3"]["show"] is True  # Unchanged

    def test_set_multiple_field_display_with_field_list(self):
        """Test setting display for multiple fields using field list."""
        build_config = dotdict({"field1": {"show": True}, "field2": {"show": True}, "field3": {"show": True}})
        field_list = ["field1", "field2"]

        result = set_multiple_field_display(build_config, field_list=field_list, value=False)

        assert result["field1"]["show"] is False
        assert result["field2"]["show"] is False
        assert result["field3"]["show"] is True  # Unchanged

    def test_set_multiple_field_display_no_params(self):
        """Test setting multiple field display with no parameters does nothing."""
        build_config = dotdict({"field1": {"show": True}})

        result = set_multiple_field_display(build_config)

        assert result["field1"]["show"] is True  # Unchanged


class TestSetFieldAdvanced:
    """Test cases for set_field_advanced function."""

    def test_set_field_advanced_existing_field(self):
        """Test setting advanced for existing field."""
        build_config = dotdict({"field1": {"advanced": False, "other": "value"}})

        result = set_field_advanced(build_config, "field1", value=True)

        assert result["field1"]["advanced"] is True
        assert result["field1"]["other"] == "value"

    def test_set_field_advanced_default_value(self):
        """Test setting advanced with default value (None -> False)."""
        build_config = dotdict({"field1": {"other": "value"}})

        result = set_field_advanced(build_config, "field1", None)

        assert result["field1"]["advanced"] is False

    def test_set_field_advanced_non_dict_field(self):
        """Test setting advanced for non-dict field does nothing."""
        build_config = dotdict({"field1": "string_value"})

        result = set_field_advanced(build_config, "field1", value=True)

        assert result["field1"] == "string_value"  # Unchanged

    def test_set_field_advanced_creates_advanced_property(self):
        """Test that advanced property is created if it doesn't exist."""
        build_config = dotdict({"field1": {"other": "value"}})

        result = set_field_advanced(build_config, "field1", value=True)

        assert result["field1"]["advanced"] is True


class TestSetMultipleFieldAdvanced:
    """Test cases for set_multiple_field_advanced function."""

    def test_set_multiple_field_advanced_with_fields_dict(self):
        """Test setting advanced for multiple fields using fields dict."""
        build_config = dotdict({"field1": {"advanced": False}, "field2": {"advanced": False}})
        fields = {"field1": True, "field2": False}

        result = set_multiple_field_advanced(build_config, fields=fields)

        assert result["field1"]["advanced"] is True
        assert result["field2"]["advanced"] is False

    def test_set_multiple_field_advanced_with_field_list(self):
        """Test setting advanced for multiple fields using field list."""
        build_config = dotdict({"field1": {"advanced": False}, "field2": {"advanced": False}})
        field_list = ["field1", "field2"]

        result = set_multiple_field_advanced(build_config, field_list=field_list, value=True)

        assert result["field1"]["advanced"] is True
        assert result["field2"]["advanced"] is True


class TestMergeBuildConfigs:
    """Test cases for merge_build_configs function."""

    def test_merge_build_configs_simple(self):
        """Test merging simple build configurations."""
        base_config = dotdict({"field1": "base_value", "field2": "base_value2"})
        override_config = dotdict({"field1": "override_value", "field3": "new_value"})

        result = merge_build_configs(base_config, override_config)

        assert result["field1"] == "override_value"  # Overridden
        assert result["field2"] == "base_value2"  # From base
        assert result["field3"] == "new_value"  # Added

    def test_merge_build_configs_nested_dicts(self):
        """Test merging build configurations with nested dictionaries."""
        base_config = dotdict({"field1": {"nested1": "base_value", "nested2": "base_value2"}})
        override_config = dotdict({"field1": {"nested1": "override_value", "nested3": "new_value"}})

        result = merge_build_configs(base_config, override_config)

        assert result["field1"]["nested1"] == "override_value"
        assert result["field1"]["nested2"] == "base_value2"
        assert result["field1"]["nested3"] == "new_value"

    def test_merge_build_configs_returns_new_object(self):
        """Test that merge returns a new dotdict object."""
        base_config = dotdict({"field1": "base_value"})
        override_config = dotdict({"field2": "override_value"})

        result = merge_build_configs(base_config, override_config)

        assert result is not base_config
        assert isinstance(result, dotdict)

    def test_merge_build_configs_override_dict_with_non_dict(self):
        """Test overriding dict with non-dict value."""
        base_config = dotdict({"field1": {"nested": "value"}})
        override_config = dotdict({"field1": "string_value"})

        result = merge_build_configs(base_config, override_config)

        assert result["field1"] == "string_value"


class TestSetCurrentFields:
    """Test cases for set_current_fields function."""

    def test_set_current_fields_with_selected_action(self):
        """Test setting current fields with a selected action."""
        build_config = dotdict(
            {
                "field1": {"show": False},
                "field2": {"show": False},
                "field3": {"show": False},
                "code": {"show": False},
                "_type": {"show": False},
            }
        )
        action_fields = {"action1": ["field1", "field2"], "action2": ["field3"]}

        result = set_current_fields(build_config, action_fields, "action1")

        # Selected action fields should be shown
        assert result["field1"]["show"] is True
        assert result["field2"]["show"] is True
        # Other action fields should be hidden
        assert result["field3"]["show"] is False
        # Default fields should be shown
        assert result["code"]["show"] is True
        assert result["_type"]["show"] is True

    def test_set_current_fields_no_selected_action(self):
        """Test setting current fields with no selected action."""
        build_config = dotdict({"field1": {"show": True}, "field2": {"show": True}, "code": {"show": False}})
        action_fields = {"action1": ["field1"], "action2": ["field2"]}

        result = set_current_fields(build_config, action_fields, None)

        # All action fields should be hidden
        assert result["field1"]["show"] is False
        assert result["field2"]["show"] is False
        # Default fields should be shown
        assert result["code"]["show"] is True

    def test_set_current_fields_custom_function(self):
        """Test setting current fields with custom function."""
        build_config = dotdict(
            {"field1": {"advanced": False}, "field2": {"advanced": False}, "code": {"advanced": False}}
        )
        action_fields = {"action1": ["field1"], "action2": ["field2"]}

        result = set_current_fields(build_config, action_fields, "action1", func=set_field_advanced)

        # Selected field should be True (not default_value)
        assert result["field1"]["advanced"] is True  # Selected field gets not default_value (True)
        assert result["field2"]["advanced"] is False  # Non-selected field gets default_value (False)
        assert result["code"]["advanced"] is True  # Default field gets not default_value (True)

    def test_set_current_fields_custom_default_value(self):
        """Test setting current fields with custom default value."""
        build_config = dotdict({"field1": {"show": False}, "field2": {"show": False}, "code": {"show": False}})
        action_fields = {"action1": ["field1"], "action2": ["field2"]}

        result = set_current_fields(
            build_config,
            action_fields,
            "action1",
            default_value=True,  # Inverted logic
        )

        # With default_value=True:
        # - Selected field gets not default_value = False
        # - Non-selected fields get default_value = True
        # - Default fields get not default_value = False
        assert result["field1"]["show"] is False  # Selected field gets not default_value
        assert result["field2"]["show"] is True  # Non-selected field gets default_value
        assert result["code"]["show"] is False  # Default field gets not default_value

    def test_set_current_fields_no_default_fields(self):
        """Test setting current fields with no default fields."""
        build_config = dotdict({"field1": {"show": False}, "code": {"show": False}})
        action_fields = {"action1": ["field1"]}

        result = set_current_fields(build_config, action_fields, "action1", default_fields=None)

        # Only action field should be affected
        assert result["field1"]["show"] is True
        assert result["code"]["show"] is False  # Unchanged

    def test_default_fields_constant(self):
        """Test that DEFAULT_FIELDS constant has expected value."""
        assert DEFAULT_FIELDS == ["code", "_type"]
