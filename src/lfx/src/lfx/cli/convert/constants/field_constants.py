"""Field filtering and validation constants for flow conversion."""

from __future__ import annotations

# Fields to skip when parsing node configuration (internal/UI fields)
SKIP_FIELDS: frozenset[str] = frozenset(
    {
        "code",
        "_type",
        "_frontend_node_flow_id",
        "_frontend_node_folder_id",
        "show",
        "advanced",
        "dynamic",
        "info",
        "display_name",
        "required",
        "placeholder",
        "list",
        "multiline",
        "input_types",
        "output_types",
        "file_path",
        "fileTypes",
        "password",
        "load_from_db",
        "title_case",
        "real_time_refresh",
        "refresh_button",
        "trace_as_input",
        "trace_as_metadata",
        "_input_type",
        "list_add_label",
        "name",
        "type",
        "options",
        "tool_mode",
        "track_in_telemetry",
        "copy_field",
        "ai_enabled",
        "override_skip",
        # JSON-only fields not present in lfx components
        "mode",
        "use_double_brackets",
    }
)

# Fields that contain long text to be extracted as constants
LONG_TEXT_FIELDS: frozenset[str] = frozenset(
    {
        "system_prompt",
        "prompt",
        "template",
        "agent_description",
        "format_instructions",
    }
)

# Minimum length for a field to be considered "long text"
MIN_PROMPT_LENGTH = 200

# Python reserved words that cannot be used as variable names
PYTHON_RESERVED_WORDS: frozenset[str] = frozenset(
    {
        # Python keywords
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        # Python builtins that shouldn't be shadowed
        "input",
        "output",
        "type",
        "id",
        "list",
        "dict",
        "set",
        "str",
        "int",
        "float",
        "bool",
        "None",
        "True",
        "False",
    }
)

# UI-only node types to skip during conversion
# These are purely visual/UI elements in Langflow with no runtime behavior
SKIP_NODE_TYPES: frozenset[str] = frozenset(
    {
        "",  # Empty type (often ReadMe or undefined nodes)
        "note",
        "Note",
        "NoteNode",
        "undefined",
        "Undefined",
        "ReadMe",
        "readme",
        "StickyNote",
        "sticky_note",
        "CommentNode",
        "comment",
    }
)

# Input types that might be used in custom component code
# Used when parsing custom components to generate proper imports
KNOWN_INPUT_TYPES: frozenset[str] = frozenset(
    {
        "BoolInput",
        "DataInput",
        "DataFrameInput",
        "DictInput",
        "DropdownInput",
        "FileInput",
        "FloatInput",
        "HandleInput",
        "IntInput",
        "LinkInput",
        "MessageInput",
        "MessageTextInput",
        "MultilineInput",
        "MultilineSecretInput",
        "MultiselectInput",
        "NestedDictInput",
        "Output",
        "PromptInput",
        "SecretStrInput",
        "SliderInput",
        "StrInput",
        "TableInput",
        "TabInput",
    }
)
