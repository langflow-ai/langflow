"""Component operations: add, remove, configure, list components in flows.

Pure functions that operate on flow dicts. The component registry is passed
as a parameter (dict mapping component_type -> template_dict), not loaded
from global state.

All functions are pure — no I/O, no network, no global state.
"""

from __future__ import annotations

import copy
import secrets
import string
from typing import Any

from lfx.graph.flow_builder._utils import node_id as _node_id


def _generate_id(component_type: str) -> str:
    """Generate a component ID like 'ChatInput-a1B2c'."""
    suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(5))
    return f"{component_type}-{suffix}"


def _make_node(
    component_type: str,
    registry: dict[str, dict],
    component_id: str | None = None,
) -> dict:
    """Create a full node structure from the component registry.

    Args:
        component_type: The type name (e.g. "ChatInput").
        registry: Mapping of component_type -> template dict.
        component_id: Optional explicit ID; auto-generated if None.
    """
    cid = component_id or _generate_id(component_type)

    if component_type not in registry:
        available = ", ".join(sorted(registry.keys())[:20])
        msg = f"Unknown component: {component_type}. Available: {available}..."
        raise ValueError(msg)

    node_data = copy.deepcopy(registry[component_type])

    return {
        "id": cid,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "selected": False,
        "data": {
            "id": cid,
            "type": component_type,
            "node": node_data,
            "showNode": True,
        },
    }


def add_component(
    flow: dict,
    component_type: str,
    registry: dict[str, dict],
    component_id: str | None = None,
) -> dict:
    """Add a component to a flow with its full template from the registry.

    Returns dict with 'id' and 'display_name'.
    """
    node = _make_node(component_type, registry, component_id=component_id)
    flow["data"]["nodes"].append(node)
    return {"id": node["id"], "display_name": node["data"]["node"].get("display_name", component_type)}


def remove_component(flow: dict, component_id: str) -> None:
    """Remove a component and all its connections from a flow."""
    nodes = flow["data"]["nodes"]
    original_count = len(nodes)
    flow["data"]["nodes"] = [n for n in nodes if _node_id(n) != component_id]
    if len(flow["data"]["nodes"]) == original_count:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    edges = flow["data"]["edges"]
    flow["data"]["edges"] = [e for e in edges if e.get("source") != component_id and e.get("target") != component_id]


def configure_component(
    flow: dict,
    component_id: str,
    params: dict[str, Any],
) -> None:
    """Set parameters on a component (pure version — no server calls)."""
    node = _find_node(flow, component_id)
    if node is None:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    template = node["data"].setdefault("node", {}).setdefault("template", {})
    for key, value in params.items():
        if key not in template:
            available = [k for k in template if isinstance(template[k], dict)]
            msg = f"Unknown parameter '{key}' on component '{component_id}'. Available: {available}"
            raise ValueError(msg)
        if isinstance(template[key], dict):
            template[key]["value"] = value
        else:
            template[key] = {"value": value}


def get_component(flow: dict, component_id: str) -> dict:
    """Get information about a component in a flow."""
    node = _find_node(flow, component_id)
    if node is None:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    node_data = node.get("data", {})
    node_config = node_data.get("node", {})
    template = node_config.get("template", {})

    params = {}
    for key, field in template.items():
        if isinstance(field, dict):
            params[key] = field.get("value")

    return {
        "id": _node_id(node),
        "display_name": node_config.get("display_name", node_data.get("type", "")),
        "type": node_data.get("type", ""),
        "params": params,
        "outputs": node_config.get("outputs", []),
    }


def list_components(flow: dict) -> list[dict]:
    """List all components in a flow."""
    results = []
    for node in flow.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        node_config = node_data.get("node", {})
        results.append(
            {
                "id": _node_id(node),
                "display_name": node_config.get("display_name", node_data.get("type", "")),
                "type": node_data.get("type", ""),
            }
        )
    return results


def needs_server_update(template: dict, field: str) -> bool:
    """Check if setting a field requires server-side template regeneration.

    The frontend triggers /custom_component/update on value change only when
    the field has real_time_refresh=True. tool_mode is handled separately.
    """
    if field == "tool_mode":
        return True
    field_def = template.get(field, {})
    if not isinstance(field_def, dict):
        return False
    return bool(field_def.get("real_time_refresh"))


def _find_node(flow: dict, component_id: str) -> dict | None:
    """Find a node by component ID."""
    for node in flow.get("data", {}).get("nodes", []):
        if _node_id(node) == component_id:
            return node
    return None
