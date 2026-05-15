"""Compatibility checker: Python port of check-code-validity.ts."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

COMPONENTS_TO_IGNORE_UPDATE: frozenset[str] = frozenset({"CustomComponent"})

NodeStatusLiteral = Literal["ok", "outdated_safe", "outdated_breaking", "blocked"]


@dataclass
class NodeStatus:
    node_id: str
    component_type: str
    display_name: str
    status: NodeStatusLiteral


@dataclass
class CompatibilityReport:
    nodes: list[NodeStatus] = field(default_factory=list)

    @property
    def has_blocked(self) -> bool:
        return any(n.status == "blocked" for n in self.nodes)

    @property
    def has_breaking(self) -> bool:
        return any(n.status == "outdated_breaking" for n in self.nodes)

    @property
    def has_safe_updates(self) -> bool:
        return any(n.status == "outdated_safe" for n in self.nodes)

    @property
    def is_clean(self) -> bool:
        return not self.nodes or all(n.status == "ok" for n in self.nodes)


def build_registry_lookup(all_types_dict: Mapping[str, Any]) -> dict[str, dict]:
    """Flatten all_types_dict into {component_type: component_data}."""
    lookup: dict[str, dict] = {}
    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue
        for comp_name, comp_data in category_components.items():
            if isinstance(comp_data, Mapping):
                lookup[comp_name] = dict(comp_data)
    return lookup


def _outputs_are_equal(original: list[dict], user: list[dict]) -> bool:
    user_map = {o["name"]: o for o in user}
    orig_names = {o["name"] for o in original}
    if orig_names != set(user_map):
        return False
    for orig in original:
        u = user_map.get(orig["name"])
        if u is None:
            return False
        if (
            orig.get("display_name") != u.get("display_name")
            or sorted(orig.get("types") or []) != sorted(u.get("types") or [])
            or orig.get("method") != u.get("method")
            or orig.get("allows_loop") != u.get("allows_loop")
        ):
            return False
    return True


def _template_keys_equal(original: dict, user: dict) -> bool:
    return sorted(original) == sorted(user)


def _input_types_contained(original: dict, user: dict) -> bool:
    """Check that all original input_types are present in user, AND user has no extra types the registry removed."""
    for key, orig_field in original.items():
        if not isinstance(orig_field, Mapping):
            continue
        orig_types = orig_field.get("input_types")
        if not orig_types:
            continue
        user_field = user.get(key)
        if not user_field:
            return False
        user_types = user_field.get("input_types") or []
        # All registry types must be supported by the node
        if not all(t in user_types for t in orig_types):
            return False
        # All node types must still be accepted by the registry (narrowing is a breaking change)
        if not all(t in orig_types for t in user_types):
            return False
    return True


def _has_breaking_change(registry_entry: dict, node_info: dict) -> bool:
    orig_outputs = registry_entry.get("outputs") or []
    user_outputs = node_info.get("outputs") or []
    if orig_outputs and not _outputs_are_equal(orig_outputs, user_outputs):
        return True
    orig_template = registry_entry.get("template") or {}
    user_template = node_info.get("template") or {}
    if orig_template and not _template_keys_equal(orig_template, user_template):
        return True
    if orig_template and not _input_types_contained(orig_template, user_template):
        return True
    return False


def _classify_node(node: dict, registry: dict[str, dict]) -> NodeStatus | None:
    data = node.get("data", {})
    node_info = data.get("node", {})
    component_type = data.get("type", "")
    node_id = data.get("id") or node.get("id", "unknown")
    display_name = node_info.get("display_name") or component_type

    node_template = node_info.get("template", {})
    code_field = node_template.get("code")
    node_code = code_field.get("value") if isinstance(code_field, dict) else None
    if not node_code:
        return None

    if component_type in COMPONENTS_TO_IGNORE_UPDATE:
        return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="ok")

    registry_entry = registry.get(component_type)
    if registry_entry is None:
        return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="blocked")

    registry_template = registry_entry.get("template", {})
    registry_code_field = registry_template.get("code")
    registry_code = registry_code_field.get("value") if isinstance(registry_code_field, dict) else None

    if registry_code is None or node_code == registry_code:
        return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="ok")

    if _has_breaking_change(registry_entry, node_info):
        return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="outdated_breaking")

    return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="outdated_safe")


def check_flow_compatibility(
    flow_data: dict,
    all_types_dict: Mapping[str, Any],
) -> CompatibilityReport:
    """Check all nodes in flow_data against the component registry."""
    registry = build_registry_lookup(all_types_dict)
    nodes = flow_data.get("nodes", [])
    statuses: list[NodeStatus] = []
    for node in nodes:
        status = _classify_node(node, registry)
        if status is not None:
            statuses.append(status)
        node_info = node.get("data", {}).get("node", {})
        nested_nodes = node_info.get("flow", {}).get("data", {}).get("nodes", [])
        for nested_node in nested_nodes:
            ns = _classify_node(nested_node, registry)
            if ns is not None:
                statuses.append(ns)
    return CompatibilityReport(nodes=statuses)
