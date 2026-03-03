"""Constants for dynamic agent flow generation."""

CHAT_INPUT_TYPE = "ChatInput"
AGENT_TYPE = "Agent"
CHAT_OUTPUT_TYPE = "ChatOutput"

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant that can use tools to answer questions and perform tasks."

# Node template definitions — minimal required structure for aload_flow_from_json.
# Every field MUST include "show": True, otherwise the param_handler skips it
# during vertex parameter processing (see should_skip_field in param_handler.py).

CHAT_INPUT_TEMPLATE: dict = {
    "_type": "Component",
    "input_value": {
        "_input_type": "MultilineInput",
        "type": "str",
        "show": True,
        "value": "",
        "input_types": [],
    },
    "sender": {"type": "str", "show": True, "value": "User"},
    "sender_name": {"type": "str", "show": True, "value": "User"},
    "session_id": {"type": "str", "show": True, "value": ""},
    "should_store_message": {"type": "bool", "show": True, "value": True},
}

CHAT_OUTPUT_TEMPLATE: dict = {
    "_type": "Component",
    "input_value": {
        "_input_type": "HandleInput",
        "type": "other",
        "show": True,
        "input_types": ["Data", "DataFrame", "Message"],
        "required": True,
        "value": "",
    },
    "sender": {"type": "str", "show": True, "value": "Machine"},
    "sender_name": {"type": "str", "show": True, "value": "AI"},
    "session_id": {"type": "str", "show": True, "value": ""},
    "should_store_message": {"type": "bool", "show": True, "value": True},
    "data_template": {"type": "str", "show": True, "value": "{text}"},
    "clean_data": {"type": "bool", "show": True, "value": True},
}

DEFAULT_FORMAT_INSTRUCTIONS = (
    "You are an AI that extracts structured JSON objects from unstructured text. "
    "Use a predefined schema with expected types (str, int, float, bool, dict). "
    "Extract ALL relevant instances that match the schema - if multiple patterns exist, capture them all. "
    "Fill missing or ambiguous values with defaults: null for missing values. "
    "Remove exact duplicates but keep variations that have different field values. "
    "Always return valid JSON in the expected format, never throw errors. "
    "If multiple objects can be extracted, return them all in the structured format."
)

AGENT_TEMPLATE: dict = {
    "_type": "Component",
    "model": {
        "_input_type": "ModelInput",
        "type": "model",
        "show": True,
        "input_types": ["LanguageModel"],
        "required": True,
        "real_time_refresh": True,
        "refresh_button": True,
        "placeholder": "Setup Provider",
        "value": [],
    },
    "api_key": {
        "_input_type": "SecretStrInput",
        "type": "str",
        "show": True,
        "password": True,
        "advanced": True,
        "value": "",
    },
    "base_url_ibm_watsonx": {
        "_input_type": "DropdownInput",
        "type": "str",
        "show": False,
        "advanced": True,
        "value": "https://us-south.ml.cloud.ibm.com",
    },
    "project_id": {
        "type": "str",
        "show": False,
        "advanced": True,
        "required": False,
        "value": "",
    },
    "system_prompt": {
        "_input_type": "MultilineInput",
        "type": "str",
        "show": True,
        "advanced": False,
        "multiline": True,
        "value": "",
    },
    "context_id": {
        "_input_type": "MessageTextInput",
        "type": "str",
        "show": True,
        "advanced": True,
        "value": "",
    },
    "tools": {
        "_input_type": "HandleInput",
        "type": "other",
        "show": True,
        "input_types": ["Tool"],
        "list": True,
        "advanced": False,
        "value": "",
    },
    "input_value": {
        "_input_type": "MessageInput",
        "type": "str",
        "show": True,
        "input_types": ["Message"],
        "advanced": False,
        "tool_mode": True,
        "value": "",
    },
    "max_iterations": {"type": "int", "show": True, "value": 15, "advanced": True},
    "max_tokens": {"type": "int", "show": True, "value": 0, "advanced": True},
    "n_messages": {"type": "int", "show": True, "value": 100, "advanced": True},
    "format_instructions": {
        "_input_type": "MultilineInput",
        "type": "str",
        "show": True,
        "advanced": True,
        "multiline": True,
        "value": DEFAULT_FORMAT_INSTRUCTIONS,
    },
    "output_schema": {
        "_input_type": "TableInput",
        "type": "table",
        "show": True,
        "advanced": True,
        "required": False,
        "value": [],
    },
    "handle_parsing_errors": {"type": "bool", "show": True, "value": True, "advanced": True},
    "verbose": {"type": "bool", "show": True, "value": True, "advanced": True},
    "add_current_date_tool": {"type": "bool", "show": True, "value": False, "advanced": True},
    "agent_description": {
        "type": "str",
        "show": True,
        "value": "A helpful assistant with access to the following tools:",
        "advanced": True,
    },
}

TOOL_OUTPUT = {
    "display_name": "Toolset",
    "method": "to_toolkit",
    "name": "component_as_tool",
    "selected": "Tool",
    "tool_mode": True,
    "types": ["Tool"],
}
