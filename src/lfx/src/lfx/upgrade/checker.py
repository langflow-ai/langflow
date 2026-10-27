"""Compatibility checker: Python port of check-code-validity.ts."""

from __future__ import annotations

import json
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from lfx.utils.flow_code import normalize_code_for_import

COMPONENTS_TO_IGNORE_UPDATE: frozenset[str] = frozenset({"CustomComponent"})
# Template keys that are editor runtime metadata, not component fields. Must be the same set as
# transientTemplateKeys in src/frontend/src/CustomNodes/helpers/check-code-validity.ts.
TRANSIENT_TEMPLATE_KEYS: frozenset[str] = frozenset({"is_refresh", "tools_metadata"})

# Synthetic output name a component receives when it is switched to tool mode. Must match
# lfx.base.tools.constants.TOOL_OUTPUT_NAME, duplicated as a literal for the same reason
# lfx.graph.flow_builder.connect does it: to keep this module free of lfx.base imports.
TOOL_OUTPUT_NAME = "component_as_tool"

NodeStatusLiteral = Literal["ok", "outdated_safe", "outdated_breaking", "blocked", "retired", "customized"]
BreakingReasonCode = Literal[
    "output_changed", "field_removed", "required_input_missing", "connection_dropped", "value_dropped"
]


@dataclass(frozen=True)
class BreakingReason:
    """One way updating a saved node breaks it.

    ``field`` is the template field, or the output for ``output_changed``. It is ``None`` when the
    reason has no single field.
    """

    code: BreakingReasonCode
    field: str | None
    message: str


@dataclass
class NodeStatus:
    node_id: str
    component_type: str
    display_name: str
    status: NodeStatusLiteral
    retired_in: str | None = None
    replacement: list[str] = field(default_factory=list)


@dataclass
class CompatibilityReport:
    nodes: list[NodeStatus] = field(default_factory=list)

    @property
    def has_blocked(self) -> bool:
        return any(n.status == "blocked" for n in self.nodes)

    @property
    def has_retired(self) -> bool:
        return any(n.status == "retired" for n in self.nodes)

    @property
    def has_customized(self) -> bool:
        return any(n.status == "customized" for n in self.nodes)

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


def _canonical_types(types: Any) -> set[str]:
    """Return a type list as a set, with historical type names mapped to their current names.

    ``Data`` and ``JSON``, ``DataFrame`` and ``Table`` are the same type: an edge saved with the
    old name still connects (``lfx.graph.edge.base.TYPE_MIGRATIONS``, mirrored by
    ``TYPE_MIGRATIONS`` in ``src/frontend/src/constants/constants.ts``).
    """
    from lfx.graph.edge.base import TYPE_MIGRATIONS

    return {TYPE_MIGRATIONS.get(t, t) for t in types or []}


def _output_reasons(registry_outputs: list[dict], flow_outputs: list[dict]) -> Iterator[BreakingReason]:
    """Yield a reason for every output the saved node has that changed enough to drop its edges.

    Breaking, for an output the saved node has:
      - removed or renamed (a component that declares no outputs removes them all),
      - a changed ``method`` or ``allows_loop``,
      - **narrowed** types: the registry dropped a type the saved flow emitted.

    An **added** output, a cosmetic ``display_name`` change, **widened** types, a reordered type
    list, and a historical type name (``Data`` saved, ``JSON`` declared) are not breaking and must
    not be flagged, otherwise ``--upgrade-flow=safe`` would needlessly abort on a string edit.
    """
    registry_map = {o["name"]: o for o in registry_outputs}
    for flow_output in flow_outputs:
        name = flow_output["name"]
        reg = registry_map.get(name)
        if reg is None:
            yield BreakingReason("output_changed", name, f"{name} was removed or renamed")
            continue
        # narrowing breaks edges; widening is safe
        dropped = _canonical_types(flow_output.get("types")) - _canonical_types(reg.get("types"))
        if dropped:
            yield BreakingReason("output_changed", name, f"{name} no longer outputs {', '.join(sorted(dropped))}")
        if reg.get("method") != flow_output.get("method"):
            yield BreakingReason("output_changed", name, f"{name} changed method")
        if reg.get("allows_loop") != flow_output.get("allows_loop"):
            yield BreakingReason("output_changed", name, f"{name} changed allows_loop")


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


def _custom_field_names(node_info: Mapping[str, Any]) -> set[str]:
    """Return the fields the saved node lists in ``custom_fields``.

    A Prompt saves ``{"template": ["question", ...]}``: one field per template variable. The
    component rebuilds those fields from the saved template text when the node is updated, so
    they are not fields the component dropped.
    """
    custom_fields = node_info.get("custom_fields")
    if not isinstance(custom_fields, Mapping):
        return set()
    return {name for names in custom_fields.values() if isinstance(names, list) for name in names}


def _template_key_reasons(
    registry_template: dict, flow_template: dict, custom_field_names: Collection[str] = ()
) -> Iterator[BreakingReason]:
    """Yield a reason for every template key difference an update cannot absorb.

    Template key sets are compared directionally, not for equality:

    - A field only the *flow* has is one the registry dropped, or one the component added
      while it was edited (Run Flow inputs, MCP Tools arguments). Updating the node drops the
      field, its value, and any edge into it, so it is always breaking, connected or not. The
      exception is a field the node lists in ``custom_fields`` (Prompt variables), which the
      component rebuilds.
    - A field only the *registry* has is one the saved flow predates — the evolution the
      contributing docs recommend as non-breaking. ``apply_safe_upgrades`` introduces it
      exactly as the registry declares it, so it only breaks when that declared state is
      unusable: a *required* field with nothing to fill it, which would turn a flow that
      ran into one that fails asking for input.
    """
    saved_only = _structural_template_keys(flow_template) - _structural_template_keys(registry_template)
    for key in sorted(saved_only - set(custom_field_names)):
        yield BreakingReason("field_removed", key, f"the component no longer has {key}")
    for key in sorted(new_template_field_keys(registry_template, flow_template)):
        field = registry_template.get(key)
        if isinstance(field, Mapping) and field.get("required") and field.get("value") in (None, ""):
            yield BreakingReason("required_input_missing", key, f"{key} is a new required field with no value")


def _holds_value(field: Mapping[str, Any]) -> bool:
    """Return True when a saved field holds a value: anything but ``None``, ``""``, ``[]`` or ``{}``."""
    return field.get("value") not in (None, "", [], {})


def retyped_field_keys(registry_template: Mapping[str, Any], flow_template: Mapping[str, Any]) -> set[str]:
    """Return the fields both sides have whose ``type`` changed.

    On a node the checker calls safe these fields are empty and unconnected, so
    ``apply_safe_upgrades`` replaces each one with the registry's declaration, as the editor does.
    """
    return {
        key
        for key in _structural_template_keys(flow_template) & _structural_template_keys(registry_template)
        if isinstance(registry_template[key], Mapping)
        and isinstance(flow_template[key], Mapping)
        and registry_template[key].get("type") != flow_template[key].get("type")
    }


def _shared_field_reasons(
    registry_template: dict,
    flow_template: dict,
    connected_fields: Collection[str] | None,
    *,
    in_tool_mode: bool = False,
) -> Iterator[BreakingReason]:
    """Yield a reason for every field both sides have that loses its saved edges or its saved value.

    ``connected_fields`` of ``None`` means the connections are unknown, so every field counts as
    connected. A field gets at most one reason: a retyped field that is connected and holds a value
    reports the dropped connection.

    - A changed field ``type`` is breaking when an edge goes into the field, because the editor
      keeps an edge only when the handle's field ``type`` is equal. It is also breaking when the
      saved field holds a value, because an update copies a saved value only when the field
      ``type`` is equal (``lfx.template.utils.update_template_field``).
    - Every type a connected field accepted must still be accepted (historical type names count
      as the same type). Narrowing breaks the saved edges, and an emptied ``input_types`` list
      means the field no longer takes connections at all. Widening is safe.
    - On a node in tool mode, a connected field the component now marks ``tool_mode`` is
      breaking: the editor drops edges into tool-mode fields of a tool-mode node.
    """
    for key in sorted(_structural_template_keys(flow_template) & _structural_template_keys(registry_template)):
        registry_field, flow_field = registry_template[key], flow_template[key]
        if not isinstance(registry_field, Mapping) or not isinstance(flow_field, Mapping):
            continue
        connected = connected_fields is None or key in connected_fields
        retyped = registry_field.get("type") != flow_field.get("type")
        if retyped and connected:
            yield BreakingReason("connection_dropped", key, f"{key} changed type and has a connection")
        elif retyped and _holds_value(flow_field):
            yield BreakingReason("value_dropped", key, f"{key} changed type and its value would be dropped")
        elif connected and (
            dropped := _canonical_types(flow_field.get("input_types"))
            - _canonical_types(registry_field.get("input_types"))
        ):
            yield BreakingReason(
                "connection_dropped", key, f"{key} no longer accepts {', '.join(sorted(dropped))} and has a connection"
            )
        elif connected and in_tool_mode and registry_field.get("tool_mode") and not flow_field.get("tool_mode"):
            yield BreakingReason("connection_dropped", key, f"{key} became a tool input and has a connection")


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


def has_breaking_change(
    registry_entry: Mapping[str, Any],
    node_info: Mapping[str, Any],
    connected_fields: Collection[str] | None = None,
) -> bool:
    """Return True when re-stamping this node with the registry's code would break it.

    A change is breaking when updating the node drops a connection, drops a value, or needs
    input nobody gave. Must match ``codeHasBreakingChange`` in
    ``src/frontend/src/CustomNodes/helpers/check-code-validity.ts``; both run the shared cases in
    ``src/lfx/tests/data/component_compat/cases.json``.

    Public because the restricted-mode build path reports the same condition: there a saved
    node's code is replaced by this server's copy for the same component type, so a node the
    checker calls breaking is one whose saved configuration cannot drive the component that
    actually runs. See ``describe_restricted_component_mismatch``.

    ``connected_fields`` names the fields a connection goes into. ``None`` (the default) means
    the connections are unknown, so every field counts as connected. ``breaking_reasons`` says why.
    """
    return bool(breaking_reasons(registry_entry, node_info, connected_fields))


def breaking_reasons(
    registry_entry: Mapping[str, Any],
    node_info: Mapping[str, Any],
    connected_fields: Collection[str] | None = None,
) -> list[BreakingReason]:
    """List every way re-stamping this node with the registry's code would break it.

    The rule of ``has_breaking_change``, which is True exactly when this list is not empty. It
    keeps checking after the first reason, so a report can name everything that breaks.
    """
    reasons: list[BreakingReason] = []
    registry_outputs = registry_entry.get("outputs") or []
    if node_info.get("outputs") is None and registry_outputs:
        # Without saved outputs nothing tells which outputs had edges, so assume they all did.
        reasons.append(BreakingReason("output_changed", None, "the saved node lists no outputs"))
    flow_outputs = node_info.get("outputs") or []
    in_tool_mode = _node_is_in_tool_mode(flow_outputs)
    if in_tool_mode:
        # A tool-mode node's saved outputs are the toolset projection, so they never match the
        # registry's declared outputs and comparing the two always reports a breaking change.
        # What matters for such a node is whether the component still supports tool mode. A
        # removed or renamed output cannot disconnect its edges, because its only output is
        # the toolset.
        if not _registry_supports_tool_mode(registry_entry):
            reasons.append(
                BreakingReason("output_changed", TOOL_OUTPUT_NAME, "the component no longer supports tool mode")
            )
    else:
        reasons.extend(_output_reasons(registry_outputs, flow_outputs))
    registry_template = registry_entry.get("template") or {}
    flow_template = node_info.get("template") or {}
    if registry_template:
        reasons.extend(_template_key_reasons(registry_template, flow_template, _custom_field_names(node_info)))
        reasons.extend(
            _shared_field_reasons(registry_template, flow_template, connected_fields, in_tool_mode=in_tool_mode)
        )
    return reasons


def flow_node_id(node: Mapping[str, Any]) -> str:
    """Return the id a flow's edges use for ``node``: its top-level ``id``, as the runtime and the editor read it."""
    return node.get("id") or node.get("data", {}).get("id") or "unknown"


def _classify_node(
    node: dict, registry: dict[str, dict], connected_fields: Collection[str] | None = None
) -> NodeStatus | None:
    data = node.get("data", {})
    node_info = data.get("node", {})
    component_type = data.get("type", "")
    node_id = flow_node_id(node)
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

    # A retired component fails when the flow runs, whatever its saved code, so it is reported
    # before the code comparison.
    if registry_entry.get("retired_in"):
        return NodeStatus(
            node_id=node_id,
            component_type=component_type,
            display_name=display_name,
            status="retired",
            retired_in=registry_entry["retired_in"],
            replacement=list(registry_entry.get("replacement") or []),
        )

    registry_template = registry_entry.get("template", {})
    registry_code_field = registry_template.get("code")
    registry_code = registry_code_field.get("value") if isinstance(registry_code_field, dict) else None

    if registry_code is None or node_code == registry_code:
        return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="ok")

    # The saved ``edited`` flag marks code the user changed and updates the user dismissed. Such a
    # node is never safe to overwrite, so it gets its own status before the breaking check. It comes
    # after retired: an edit of a retired component usually keeps the retired imports or base class.
    if node_info.get("edited") is True:
        return NodeStatus(
            node_id=node_id, component_type=component_type, display_name=display_name, status="customized"
        )

    if has_breaking_change(registry_entry, node_info, connected_fields):
        return NodeStatus(
            node_id=node_id, component_type=component_type, display_name=display_name, status="outdated_breaking"
        )

    return NodeStatus(node_id=node_id, component_type=component_type, display_name=display_name, status="outdated_safe")


def _target_handle(edge: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the handle an edge goes into.

    Read from ``data.targetHandle`` when it is a mapping, else from the escaped handle string the
    editor writes, else from a legacy ``type|field|node id`` string, which
    ``lfx.graph.edge.base.Edge`` still reads. Must match ``targetFieldName`` in
    ``src/frontend/src/CustomNodes/helpers/check-code-validity.ts``.
    """
    handle = (edge.get("data") or {}).get("targetHandle")
    if isinstance(handle, Mapping):
        return handle
    raw = edge.get("targetHandle")
    if not isinstance(raw, str):
        return None
    try:
        handle = json.loads(raw.replace("\u0153", '"'))
    except ValueError:
        parts = raw.split("|")
        return {"fieldName": parts[1]} if len(parts) > 1 else None
    return handle if isinstance(handle, Mapping) else None


def _connected_fields_by_node(edges: list[dict] | None) -> dict[str, set[str]] | None:
    """Map each node id to the fields a connection goes into. ``None`` when the edges are unknown."""
    if edges is None:
        return None
    connected: dict[str, set[str]] = {}
    for edge in edges:
        field_name = (_target_handle(edge) or {}).get("fieldName")
        if field_name:
            connected.setdefault(edge.get("target"), set()).add(field_name)
    return connected


def _classify_nodes_recursive(
    nodes: list[dict],
    registry: dict[str, dict],
    statuses: list[NodeStatus],
    edges: list[dict] | None,
) -> None:
    """Classify every node, recursing fully into nested grouped-component flows.

    Grouped components can nest arbitrarily deep (a group inside a group); each level lives
    under ``node.data.node.flow.data.nodes``. Walking only the first level would silently skip
    grandchildren, so we recurse all the way down, keeping the checker symmetric with the
    applier, which also recurses fully.

    ``edges`` are the edges at this level, ``None`` when they are unknown. A nested level uses the
    edges of its own flow, plus each edge into the group: it reaches the inner field that the
    edge's own ``proxy`` names, or the group field's ``proxy`` when the edge has none, as
    ``lfx.graph.graph.utils.update_target_handle`` resolves it.
    """
    connected = _connected_fields_by_node(edges)
    for node in nodes:
        node_id = flow_node_id(node)
        status = _classify_node(node, registry, None if connected is None else connected.get(node_id, set()))
        if status is not None:
            statuses.append(status)
        node_info = node.get("data", {}).get("node", {})
        nested_flow = node_info.get("flow", {}).get("data", {})
        nested = nested_flow.get("nodes")
        if nested:
            nested_edges = None
            if edges is not None and nested_flow.get("edges") is not None:
                nested_edges = list(nested_flow["edges"])
                for edge in edges:
                    handle = _target_handle(edge) if edge.get("target") == node_id else None
                    if handle is None:
                        continue
                    group_field = node_info.get("template", {}).get(handle.get("fieldName"))
                    proxy = handle.get("proxy") or (
                        group_field.get("proxy") if isinstance(group_field, Mapping) else None
                    )
                    if isinstance(proxy, Mapping):
                        nested_edges.append(
                            {"target": proxy.get("id"), "data": {"targetHandle": {"fieldName": proxy.get("field")}}}
                        )
            _classify_nodes_recursive(nested, registry, statuses, nested_edges)


def check_flow_compatibility(
    flow_data: dict,
    all_types_dict: Mapping[str, Any],
    *,
    registry: dict[str, dict] | None = None,
) -> CompatibilityReport:
    """Check all nodes in flow_data against the component registry.

    Args:
        flow_data: Parsed flow JSON with a ``nodes`` list. Its ``edges`` tell which fields a
            connection goes into. Without an ``edges`` key every field counts as connected.
        all_types_dict: Component registry (categories -> components).
        registry: Optional pre-built lookup from ``build_registry_lookup``. Pass this to avoid
            rebuilding the lookup when the caller also runs ``apply_safe_upgrades`` on the same
            registry.
    """
    flow_data = normalize_code_for_import(flow_data)
    if registry is None:
        registry = build_registry_lookup(all_types_dict)
    statuses: list[NodeStatus] = []
    _classify_nodes_recursive(flow_data.get("nodes", []), registry, statuses, flow_data.get("edges"))
    return CompatibilityReport(nodes=statuses)
