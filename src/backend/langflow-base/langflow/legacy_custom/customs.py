from langflow.template import frontend_node

# These should always be instantiated
CUSTOM_NODES: dict[str, dict[str, frontend_node.base.FrontendNode]] = {
    "custom_components": {
        "CustomComponent": frontend_node.custom_components.CustomComponentFrontendNode(),
    },
    "component": {
        "Component": frontend_node.custom_components.ComponentFrontendNode(),
    },
}


def get_custom_nodes(node_type: str):
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
