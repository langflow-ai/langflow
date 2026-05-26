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
    """Flatten all_types_dict into {component_type: component_data}, including legacy aliases.

    Uses flatten_components_with_aliases so that renamed components (e.g. Prompt →
    Prompt Template, parser → ParserComponent) are reachable under their old type key
    and are not incorrectly classified as blocked.
    """
    from lfx.utils.component_aliases import flatten_components_with_aliases

    return {k: dict(v) for k, v in flatten_components_with_aliases(all_types_dict).items() if isinstance(v, Mapping)}


def _outputs_are_compatible(registry_outputs: list[dict], flow_outputs: list[dict]) -> bool:
    """Return True if the saved flow's outputs are still valid against the registry's outputs.

    Only *breaking* differences count:
      - a changed output **name set** (a removed/renamed output breaks downstream edges),
      - a changed ``method`` or ``allows_loop``,
      - **narrowed** output types: the registry dropped a type the saved flow emitted.

    A cosmetic ``display_name`` change (e.g. a typo fix in the registry) and **widened**
    types (the registry now emits additional types) are not breaking and must not be flagged,
    otherwise ``--upgrade-flow=safe`` would needlessly abort on a string edit.
    """
    flow_map = {o["name"]: o for o in flow_outputs}
    registry_names = {o["name"] for o in registry_outputs}
    if registry_names != set(flow_map):
        return False
    for reg in registry_outputs:
        flow_output = flow_map.get(reg["name"])
        if flow_output is None:
            return False
        flow_types = set(flow_output.get("types") or [])
        registry_types = set(reg.get("types") or [])
        if (
            not flow_types.issubset(registry_types)  # narrowing breaks edges; widening is safe
            or reg.get("method") != flow_output.get("method")
            or reg.get("allows_loop") != flow_output.get("allows_loop")
        ):
            return False
    return True


def _template_keys_equal(original: dict, user: dict) -> bool:
    return sorted(original) == sorted(user)


def _input_types_contained(registry_template: dict, flow_template: dict) -> bool:
    """Return True if no input field *narrowed* its accepted ``input_types``.

    Narrowing (the registry no longer accepts a type the saved flow's edges feed into) is
    breaking. Widening (the registry accepting *more* types than before) is safe and must
    not be flagged.
    """
    for key, registry_field in registry_template.items():
        if not isinstance(registry_field, Mapping):
            continue
        registry_types = registry_field.get("input_types")
        if not registry_types:
            continue
        flow_field = flow_template.get(key)
        if not flow_field:
            return False
        flow_types = flow_field.get("input_types") or []
        # Every type the saved flow relied on must still be accepted by the registry.
        if not all(t in registry_types for t in flow_types):
            return False
    return True


def _has_breaking_change(registry_entry: dict, node_info: dict) -> bool:
    registry_outputs = registry_entry.get("outputs") or []
    flow_outputs = node_info.get("outputs") or []
    if registry_outputs and not _outputs_are_compatible(registry_outputs, flow_outputs):
        return True
    registry_template = registry_entry.get("template") or {}
    flow_template = node_info.get("template") or {}
    if registry_template and not _template_keys_equal(registry_template, flow_template):
        return True
    return bool(registry_template) and not _input_types_contained(registry_template, flow_template)


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
        return NodeStatus(
            node_id=node_id, component_type=component_type, display_name=display_name, status="outdated_breaking"
        )

    return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="outdated_safe")


def _classify_nodes_recursive(nodes: list[dict], registry: dict[str, dict], statuses: list[NodeStatus]) -> None:
    """Classify every node, recursing fully into nested grouped-component flows.

    Grouped components can nest arbitrarily deep (a group inside a group); each level lives
    under ``node.data.node.flow.data.nodes``. Walking only the first level would silently skip
    grandchildren, so we recurse all the way down, keeping the checker symmetric with the
    applier, which also recurses fully.
    """
    for node in nodes:
        status = _classify_node(node, registry)
        if status is not None:
            statuses.append(status)
        nested = node.get("data", {}).get("node", {}).get("flow", {}).get("data", {}).get("nodes")
        if nested:
            _classify_nodes_recursive(nested, registry, statuses)


def check_flow_compatibility(
    flow_data: dict,
    all_types_dict: Mapping[str, Any],
    *,
    registry: dict[str, dict] | None = None,
) -> CompatibilityReport:
    """Check all nodes in flow_data against the component registry.

    Args:
        flow_data: Parsed flow JSON with a ``nodes`` list.
        all_types_dict: Component registry (categories -> components).
        registry: Optional pre-built lookup from ``build_registry_lookup``. Pass this to avoid
            rebuilding the lookup when the caller also runs ``apply_safe_upgrades`` on the same
            registry.
    """
    if registry is None:
        registry = build_registry_lookup(all_types_dict)
    statuses: list[NodeStatus] = []
    _classify_nodes_recursive(flow_data.get("nodes", []), registry, statuses)
    return CompatibilityReport(nodes=statuses)
