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


def set_field_display(build_config: dotdict, field: str, is_visible: bool | None = None) -> dotdict:
    """Set whether a field should be displayed in the UI."""
    if field in build_config and isinstance(build_config[field], dict) and "show" in build_config[field]:
        build_config[field]["show"] = is_visible


def set_multiple_field_display(
    build_config: dotdict,
    fields: dict[str, bool] | None = None,
    is_visible: bool | None = None,
    field_list: list[str] | None = None,
) -> dotdict:
    """Set display property for multiple fields at once."""
    if fields is not None:
        for field, visibility in fields.items():
            build_config = set_field_display(build_config, field, visibility)
    elif field_list is not None:
        for field in field_list:
            build_config = set_field_display(build_config, field, is_visible)
    return build_config


def set_field_advanced(build_config: dotdict, field: str, is_advanced: bool | None = None) -> dotdict:
    """Set whether a field is considered 'advanced' in the UI."""
    if field in build_config and isinstance(build_config[field], dict):
        build_config[field]["advanced"] = is_advanced
    return build_config


def set_multiple_field_advanced(
    build_config: dotdict,
    fields: dict[str, bool] | None = None,
    is_advanced: bool | None = None,
    field_list: list[str] | None = None,
) -> dotdict:
    """Set advanced property for multiple fields at once."""
    if fields is not None:
        for field, advanced in fields.items():
            build_config = set_field_advanced(build_config, field, advanced)
    elif field_list is not None:
        for field in field_list:
            build_config = set_field_advanced(build_config, field, is_advanced)
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
) -> dotdict:
    """Set the current fields for a selected action."""
    # Update fields visibility based on selected action
    update_fields_display(build_config, action_fields, selected_action, True)

    # If no action is selected, disable the visibility of all action fields
    if selected_action is None:
        update_fields_display(build_config, action_fields, selected_action, False)

    # Always set default fields to be visible
    for field in default_fields:
        set_field_display(build_config, field, True)

    return build_config


def update_fields_display(
    build_config: dotdict, action_fields: dict[str, list[str]], selected_action: str | None, is_visible: bool
) -> None:
    for action, fields in action_fields.items():
        if action == selected_action:
            visibility = is_visible
        else:
            visibility = not is_visible
        for field in fields:
            set_field_display(build_config, field, visibility)
