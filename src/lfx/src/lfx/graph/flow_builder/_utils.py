"""Shared utilities for flow_builder modules.

Extracted here to avoid duplicating helpers across component.py, layout.py,
and other flow_builder modules that need the same node-level operations.
"""


def node_id(node: dict) -> str:
    """Extract the node ID from a node dict.

    Nodes store their ID in node["data"]["id"], falling back to node["id"].
    This was duplicated in component.py and layout.py -- consolidated here
    so both import from one place.
    """
    return node.get("data", {}).get("id", node.get("id", ""))
