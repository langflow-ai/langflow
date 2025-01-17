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
        "edit_mode": EditMode.POPOVER,
    },
    {
        "name": "tags",
        "display_name": "Tool Identifiers",
        "type": "str",
        "description": ("The default identifiers for the tools and cannot be changed."),
        "disable_edit": True,
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
    {
        "name": "commands",
        "display_name": "Commands",
        "type": "str",
        "description": (
            "Add commands to the tool. These commands will be used to run the tool. Start all commands with a `/`. "
            "You can add multiple commands separated by a comma.\n"
            "Example: `/command1`, `/command2`, `/command3`"
        ),
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
]

TOOLS_METADATA_INFO = "Modify tool names and descriptions to help agents understand when to use each tool."
