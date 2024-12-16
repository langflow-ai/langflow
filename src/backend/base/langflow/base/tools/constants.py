from langflow.schema.table import EditMode

TOOL_OUTPUT_NAME = "component_as_tool"
TOOL_OUTPUT_DISPLAY_NAME = "Toolset"
TOOLS_METADATA_INPUT_NAME = "tools_metadata"
TOOL_TABLE_SCHEMA = [
    {
        "name": "name",
        "display_name": "Tool Name",
        "type": "str",
        "description": "Specify the name of the tool.",
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
    {
        "name": "description",
        "display_name": "Tool Description",
        "type": "str",
        "description": "Describe the purpose of the tool.",
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
    {
        "name": "tags",
        "display_name": "Tool Identifiers",
        "type": "str",
        "description": (
            "These are the default identifiers for the tools and cannot be changed. "
            "Tool Name and Tool Description are the only editable fields."
        ),
        "disable_edit": True,
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
]

TOOLS_METADATA_INFO = "Use the table to configure the tools."
