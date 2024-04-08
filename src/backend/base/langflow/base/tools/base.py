from langflow.field_typing import Tool


def build_status_from_tool(tool: Tool):
    """
    Builds a status string representation of a tool.

    Args:
        tool (Tool): The tool object to build the status for.

    Returns:
        str: The status string representation of the tool, including its name, description, and arguments (if any).
    """
    description_repr = repr(tool.description).strip("'")
    args_str = "\n".join(
        [
            f"- {arg_name}: {arg_data['description']}"
            for arg_name, arg_data in tool.args.items()
            if "description" in arg_data
        ]
    )
    status = f"Name: {tool.name}\nDescription: {description_repr}"
    return status + (f"\nArguments:\n{args_str}" if args_str else "")
