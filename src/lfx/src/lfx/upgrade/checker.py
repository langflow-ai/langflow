"""Compatibility checker: Python port of check-code-validity.ts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

COMPONENTS_TO_IGNORE_UPDATE: frozenset[str] = frozenset({"CustomComponent"})
TRANSIENT_TEMPLATE_KEYS: frozenset[str] = frozenset({"is_refresh", "tools_metadata"})

# Synthetic output name a component receives when it is switched to tool mode. Must match
# lfx.base.tools.constants.TOOL_OUTPUT_NAME, duplicated as a literal for the same reason
# lfx.graph.flow_builder.connect does it: to keep this module free of lfx.base imports.
TOOL_OUTPUT_NAME = "component_as_tool"

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


def _structural_template_keys(template: Mapping[str, Any]) -> set[str]:
    """Return component fields while excluding frontend-only runtime metadata."""
    return {key for key in template if not key.startswith("_") and key not in TRANSIENT_TEMPLATE_KEYS}


def new_template_field_keys(registry_template: Mapping[str, Any], flow_template: Mapping[str, Any]) -> set[str]:
    """Return registry template fields the saved flow predates.

    These are the fields ``apply_safe_upgrades`` introduces (with their registry-declared
    state) when it re-stamps a safe node's code, so the checker's definition of a safe
    upgrade and the applier's write stay in lockstep.
    """
    return _structural_template_keys(registry_template) - _structural_template_keys(flow_template)


def _template_keys_compatible(registry_template: dict, flow_template: dict) -> bool:
    """Return True unless the registry grew a field a safe upgrade cannot fill.

    Template key sets are compared directionally, not for equality:

    - A field only the *flow* has is one the registry dropped. Its stale value is not read
      once the code is re-stamped, and ``apply_safe_upgrades`` leaves it in place, so an
      edge into it keeps its target handle.
    - A field only the *registry* has is one the saved flow predates — the evolution the
      contributing docs recommend as non-breaking. ``apply_safe_upgrades`` introduces it
      exactly as the registry declares it, so it only breaks when that declared state is
      unusable: a *required* field with nothing to fill it, which would turn a flow that
      ran into one that fails asking for input.
    """
    for key in new_template_field_keys(registry_template, flow_template):
        field = registry_template.get(key)
        if isinstance(field, Mapping) and field.get("required") and field.get("value") in (None, ""):
            return False
    return True


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
            # A field the saved flow predates has no saved edges feeding it, and
            # apply_safe_upgrades introduces it with the registry's declared input_types,
            # so there is nothing to narrow.
            continue
        flow_types = flow_field.get("input_types") or []
        # Every type the saved flow relied on must still be accepted by the registry.
        if not all(t in registry_types for t in flow_types):
            return False
    return True


def _node_is_in_tool_mode(flow_outputs: list[dict]) -> bool:
    """Return True when the saved node's outputs are the synthesized toolset output.

    Switching a component to tool mode replaces its authored outputs with a single
    ``component_as_tool`` entry, so those outputs describe a runtime projection rather than
    anything the registry declares.

    Requires *exactly* one output. A malformed node carrying the name more than once is not
    something tool mode produces, so it keeps going through the authored-output comparison.
    """
    return len(flow_outputs) == 1 and flow_outputs[0].get("name") == TOOL_OUTPUT_NAME


def _registry_supports_tool_mode(registry_entry: Mapping[str, Any]) -> bool:
    """Return True when the current component can still be switched to tool mode.

    Mirrors the input side of ``Component._handle_tool_mode``, which is what actually creates
    the ``component_as_tool`` output: a component supports tool mode when at least one input
    declares ``tool_mode``.

    Two signals are deliberately not used. The ``tool_mode`` flag on *outputs* marks which
    outputs a toolset exposes rather than the component's capability (124 of the 127 bundled
    components set it, ``ChatInput`` included). And ``add_tool_output``, the other half of the
    runtime rule, is read by neither this checker nor its frontend mirror in
    ``check-code-validity.ts``, so components that rely on it alone keep being reported
    ``outdated_breaking``; the flag is serialized into the index now, so consuming it here is a
    follow-up that has to land on both sides at once. Both omissions err the same way: a node is
    only called safe when re-stamping is known to preserve its toolset output.
    """
    template = registry_entry.get("template") or {}
    return any(isinstance(field_data, Mapping) and field_data.get("tool_mode") for field_data in template.values())


def _has_breaking_change(registry_entry: dict, node_info: dict) -> bool:
    registry_outputs = registry_entry.get("outputs") or []
    flow_outputs = node_info.get("outputs") or []
    if _node_is_in_tool_mode(flow_outputs):
        # A tool-mode node's saved outputs are the toolset projection, so they never match the
        # registry's declared outputs and comparing the two always reports a breaking change.
        # What matters for such a node is whether the component still supports tool mode. A
        # removed or renamed output cannot disconnect its edges, because its only output is
        # the toolset.
        if not _registry_supports_tool_mode(registry_entry):
            return True
    elif registry_outputs and not _outputs_are_compatible(registry_outputs, flow_outputs):
        return True
    registry_template = registry_entry.get("template") or {}
    flow_template = node_info.get("template") or {}
    if registry_template and not _template_keys_compatible(registry_template, flow_template):
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
