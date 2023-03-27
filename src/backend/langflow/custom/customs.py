from langflow.node import nodes


CUSTOM_NODES = {
    "prompts": {**nodes.ZeroShotPromptNode().to_dict()},
    "tools": {**nodes.PythonFunctionNode().to_dict(), **nodes.ToolNode().to_dict()},
}


def get_custom_nodes(node_type: str):
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
