"""This module contains constants used in the Langflow base module.

Constants:
- STREAM_INFO_TEXT: A string representing the information about streaming the response from the model.
- NODE_FORMAT_ATTRIBUTES: A list of attributes used for formatting nodes.
- FIELD_FORMAT_ATTRIBUTES: A list of attributes used for formatting fields.
- USER_PRESERVED_ATTRIBUTES: A list of field attributes that should never be overwritten (user customizations).
- VALUE_PRESERVED_ATTRIBUTES: A list of field attributes that preserve user values during updates.
- CRITICAL_UPDATE_ATTRIBUTES: A list of field attributes that should always be updated from the latest template.
"""

import orjson

STREAM_INFO_TEXT = "Stream the response from the model. Streaming works only in Chat."

NODE_FORMAT_ATTRIBUTES = [
    "beta",
    "legacy",
    "icon",
    "output_types",
    "edited",
    "metadata",
    # remove display_name to prevent overwriting the display_name from the latest template
    # "display_name",
    "description",
    "output",
    "input_types",
    "type",
    "output_types",
    "input_types",
    "type",
]

# Attributes that get updated from the latest template
FIELD_FORMAT_ATTRIBUTES = [
    # "info",
    # "display_name",
    # "required",
    # "list",
    # "multiline",
    # "combobox",
    # "fileTypes",
    # "password",
    # "title_case",
    # "real_time_refresh",
    # "refresh_button",
    # "refresh_button_text",
    # "options",
    "advanced",
    # "copy_field",
    # "dynamic",
    # "show",
    # "placeholder",
    # "range_spec",
]

# User customizations that should NEVER be overwritten during updates
USER_PRESERVED_ATTRIBUTES = [
    "value",  # User's input values
    "load_from_db",  # User's choice to load from database
    "trace_as_input",  # User's tracing preferences
    "trace_as_metadata",  # User's metadata preferences
    "name",  # Field name should not change
    "output_types",
    "input_types",
    "type",
    "_input_type",
    "show"
    "output"
]

# Attributes that preserve user values but update metadata from template
VALUE_PRESERVED_ATTRIBUTES = [
    "show"
    "value",
    "default",
    "selected",
    "load_from_db",
    "trace_as_input",
    "trace_as_metadata",
    "output_types",
    "input_types",
    "type",
    "output"
    "_input_type"
]

# Critical attributes that must always be updated for functionality
CRITICAL_UPDATE_ATTRIBUTES = [
    # "required",
    # "input_types",
    # "type",
    # "_input_type",
    # "options",
    # "range_spec",
    # "show",
    # "type"
]

# Attributes that should only be updated if they don't exist (new fields only)
ADDITIVE_ATTRIBUTES = [
    "advanced",
    "dynamic",
    "multiline",
    "password",
    "combobox",
]

ORJSON_OPTIONS = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_OMIT_MICROSECONDS
