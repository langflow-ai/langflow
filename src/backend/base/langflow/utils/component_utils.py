"""Component configuration utilities for dynamic field management in Langflow.

This module provides utilities for manipulating component build configurations,
enabling dynamic field updates, additions, deletions, and type management for
Langflow components during runtime configuration.

Key Features:
    - Dynamic build configuration manipulation
    - Field visibility and display control
    - Type inference and input type management
    - Component action handling with field filtering
    - Configuration state management utilities

Build Configuration Management:
    Components use build_config dictionaries to define their input fields,
    validation rules, and display properties. This module provides utilities
    to dynamically modify these configurations based on user selections.

Field Operations:
    - update_fields(): Modify existing field values in build configuration
    - add_fields(): Add new fields to component configuration
    - delete_fields(): Remove fields from configuration
    - get_fields(): Extract specific fields from configuration

Dynamic Field Control:
    - set_field_display(): Control field visibility based on selections
    - set_current_fields(): Manage field sets for different component actions
    - update_input_types(): Automatically update field input type constraints

Action-Based Configuration:
    Many components change their available fields based on user-selected actions.
    The utilities here support this pattern by:
    - Showing/hiding fields based on selected operations
    - Managing field sets for different component modes
    - Updating field properties dynamically

Usage Pattern:
    ```python
    def update_build_config(self, build_config, field_value, field_name):
        if field_name == "operation":
            return set_current_fields(
                build_config=build_config,
                action_fields=self.action_fields,
                selected_action=field_value,
                default_fields=["input", "operation"],
                func=set_field_display
            )
        return build_config
    ```

This module is essential for creating adaptive component interfaces that
respond to user selections and provide contextual field visibility.
"""

from collections.abc import Callable
from typing import Any

from langflow.schema.dotdict import dotdict

DEFAULT_FIELDS = ["code", "_type"]


def update_fields(build_config: dotdict, fields: dict[str, Any]) -> dotdict:
    """Update specified fields in build_config with new values."""
    for key, value in fields.items():
        if key in build_config:
            build_config[key] = value
    return build_config


def add_fields(build_config: dotdict, fields: dict[str, Any]) -> dotdict:
    """Add new fields to build_config."""
    build_config.update(fields)
    return build_config


def delete_fields(build_config: dotdict, fields: dict[str, Any] | list[str]) -> dotdict:
    """Delete specified fields from build_config."""
    if isinstance(fields, dict):
        fields = list(fields.keys())

    for field in fields:
        build_config.pop(field, None)
    return build_config


def get_fields(build_config: dotdict, fields: list[str] | None = None) -> dict[str, Any]:
    """Get fields from build_config.If fields is None, return all fields."""
    if fields is None:
        return dict(build_config)

    result = {}
    for field in fields:
        if field in build_config:
            result[field] = build_config[field]
    return result


def update_input_types(build_config: dotdict) -> dotdict:
    """Update input types for all fields in build_config."""
    for key, value in build_config.items():
        if isinstance(value, dict):
            if value.get("input_types") is None:
                build_config[key]["input_types"] = []
        elif hasattr(value, "input_types") and value.input_types is None:
            value.input_types = []
    return build_config


def set_field_display(build_config: dotdict, field: str, value: bool | None = None) -> dotdict:
    """Set whether a field should be displayed in the UI."""
    if field in build_config and isinstance(build_config[field], dict) and "show" in build_config[field]:
        build_config[field]["show"] = value
    return build_config


def set_multiple_field_display(
    build_config: dotdict,
    fields: dict[str, bool] | None = None,
    value: bool | None = None,
    field_list: list[str] | None = None,
) -> dotdict:
    """Set display property for multiple fields at once."""
    if fields is not None:
        for field, visibility in fields.items():
            build_config = set_field_display(build_config, field, visibility)
    elif field_list is not None:
        for field in field_list:
            build_config = set_field_display(build_config, field, value)
    return build_config


def set_field_advanced(build_config: dotdict, field: str, value: bool | None = None) -> dotdict:
    """Set whether a field is considered 'advanced' in the UI."""
    if value is None:
        value = False
    if field in build_config and isinstance(build_config[field], dict):
        build_config[field]["advanced"] = value
    return build_config


def set_multiple_field_advanced(
    build_config: dotdict,
    fields: dict[str, bool] | None = None,
    value: bool | None = None,
    field_list: list[str] | None = None,
) -> dotdict:
    """Set advanced property for multiple fields at once."""
    if fields is not None:
        for field, advanced in fields.items():
            build_config = set_field_advanced(build_config, field, advanced)
    elif field_list is not None:
        for field in field_list:
            build_config = set_field_advanced(build_config, field, value)
    return build_config


def merge_build_configs(base_config: dotdict, override_config: dotdict) -> dotdict:
    """Merge two build configurations, with override_config taking precedence."""
    result = dotdict(base_config.copy())
    for key, value in override_config.items():
        if key in result and isinstance(value, dict) and isinstance(result[key], dict):
            # Recursively merge nested dictionaries
            for sub_key, sub_value in value.items():
                result[key][sub_key] = sub_value
        else:
            result[key] = value
    return result


def set_current_fields(
    build_config: dotdict,
    action_fields: dict[str, list[str]],
    selected_action: str | None = None,
    default_fields: list[str] = DEFAULT_FIELDS,
    func: Callable[[dotdict, str, bool], dotdict] = set_field_display,
    default_value: bool | None = None,
) -> dotdict:
    """Set the current fields for a selected action."""
    # action_fields = {action1: [field1, field2], action2: [field3, field4]}
    # we need to show action of one field and disable the rest
    if default_value is None:
        default_value = False
    if selected_action in action_fields:
        for field in action_fields[selected_action]:
            build_config = func(build_config, field, not default_value)
        for key, value in action_fields.items():
            if key != selected_action:
                for field in value:
                    build_config = func(build_config, field, default_value)
    if selected_action is None:
        for value in action_fields.values():
            for field in value:
                build_config = func(build_config, field, default_value)
    if default_fields is not None:
        for field in default_fields:
            build_config = func(build_config, field, not default_value)
    return build_config
