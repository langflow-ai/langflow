"""Legacy custom component definitions.

This module maintains backward compatibility for legacy custom components in Langflow.
It provides predefined custom node types that are always instantiated and available
for use in flows.

The module defines:
- CustomComponent: Legacy custom component node
- Component: Standard component node

These are maintained for compatibility with older Langflow versions and flows
that may still reference these legacy component types.
"""

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
