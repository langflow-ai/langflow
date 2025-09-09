"""This module contains constants used in the Langflow base module.

Constants:
- STREAM_INFO_TEXT: A string representing the information about streaming the response from the model.
- NODE_FORMAT_ATTRIBUTES: A list of attributes used for formatting nodes.
- FIELD_FORMAT_ATTRIBUTES: A list of attributes used for formatting fields.
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
]


FIELD_FORMAT_ATTRIBUTES = [
    "info",
    "display_name",
    "required",
    "list",
    "multiline",
    "combobox",
    "fileTypes",
    "password",
    "input_types",
    "title_case",
    "real_time_refresh",
    "refresh_button",
    "refresh_button_text",
    "options",
    "advanced",
    "copy_field",
]
SKIPPED_FIELD_ATTRIBUTES = ["advanced"]
ORJSON_OPTIONS = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_OMIT_MICROSECONDS
SKIPPED_COMPONENTS = {"LanguageModelComponent"}
