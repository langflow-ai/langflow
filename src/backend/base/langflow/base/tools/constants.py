from langflow.schema.table import EditMode

TOOL_OUTPUT_NAME = "component_as_tool"
TOOL_OUTPUT_DISPLAY_NAME = "Toolset"
TOOLS_METADATA_INPUT_NAME = "tools_metadata"
TOOL_TABLE_SCHEMA = [
    {
        "name": "name",
        "display_name": "Name",
        "type": "str",
        "description": "Specify the name of the output field.",
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
    {
        "name": "description",
        "display_name": "Description",
        "type": "str",
        "description": "Describe the purpose of the output field.",
        "sortable": False,
        "filterable": False,
        "edit_mode": EditMode.INLINE,
    },
]
