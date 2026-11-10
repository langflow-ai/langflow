"""Apply safe upgrades to a flow dict.

Returns a deep copy of the flow with safe-upgradeable node codes replaced by the
current registry code, any template fields the saved flow predates introduced
with their registry defaults, any empty field whose type changed replaced by the
registry's declaration, and the outputs replaced by the registry's outputs. Breaking
and blocked nodes are left unchanged.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from lfx.template.field_migrations import can_migrate_chat_output_input
from lfx.upgrade.checker import (
    CompatibilityReport,
    _canonical_types,
    _node_is_in_tool_mode,
    build_registry_lookup,
    flow_node_id,
    new_template_field_keys,
    node_with_group_values,
    retyped_field_keys,
)


def apply_safe_upgrades(
    flow_data: dict,
    all_types_dict: Mapping[str, Any],
    report: CompatibilityReport,
    *,
    return_count: bool = False,
    registry: dict[str, dict] | None = None,
) -> dict | tuple[dict, int]:
    """Return a deep copy of flow_data with safe node codes updated.

    Args:
        flow_data: Parsed flow JSON with a ``nodes`` list.
        all_types_dict: Component registry (same shape as ``check_flow_compatibility``).
        report: Pre-computed CompatibilityReport from ``check_flow_compatibility``.
        return_count: If True, return a (flow, count) tuple where count is the
                      number of nodes that were updated.
        registry: Optional pre-built lookup from ``build_registry_lookup``. Pass this to avoid
                  rebuilding it when the caller already built it for ``check_flow_compatibility``.

    Returns:
        Updated flow dict (deep copy), or (flow, count) if return_count=True.
    """
    safe_ids = {n.node_id for n in report.nodes if n.status == "outdated_safe"}
    if not safe_ids:
        updated = copy.deepcopy(flow_data)
        return (updated, 0) if return_count else updated

    if registry is None:
        registry = build_registry_lookup(all_types_dict)
    updated = copy.deepcopy(flow_data)
    count, _ = _apply_to_nodes(updated.get("nodes", []), safe_ids, registry)

    return (updated, count) if return_count else updated


def _apply_to_nodes(nodes: list[dict], safe_ids: set[str], registry: dict[str, dict]) -> tuple[int, set[str]]:
    """Apply safe upgrades and return the ids changed at this level.

    Mirrors check_flow_compatibility's recursion into ``node.data.node.flow.data.nodes``
    so safe-upgradeable nodes inside grouped components are written, not silently skipped.
    """
    count = 0
    updated_ids: set[str] = set()
    for node in nodes:
        if flow_node_id(node) in safe_ids:
            component_type = node.get("data", {}).get("type", "")
            entry = registry.get(component_type)
            if entry:
                registry_template = entry.get("template", {})
                registry_code_field = registry_template.get("code")
                new_code = registry_code_field.get("value") if isinstance(registry_code_field, dict) else None
                if new_code is not None:
                    flow_template = node["data"]["node"]["template"]
                    flow_template["code"]["value"] = new_code
                    # The checker calls a node safe when the registry grew fields the saved
                    # flow predates; the re-stamped code reads those fields, so introduce
                    # each one exactly as the registry declares it — the state a freshly
                    # added component would carry. Deep-copied so later edits to the
                    # upgraded flow cannot reach back into the shared registry lookup.
                    # Take the registry declaration for retyped fields too. Normally those are
                    # empty and unconnected. The explicit ChatOutput migration keeps values below.
                    for key in new_template_field_keys(registry_template, flow_template) | retyped_field_keys(
                        registry_template, flow_template
                    ):
                        replacement = copy.deepcopy(registry_template[key])
                        saved_field = flow_template.get(key, {})
                        if can_migrate_chat_output_input(
                            (entry.get("metadata") or {}).get("component_class_name"),
                            key,
                            replacement,
                            saved_field,
                        ):
                            # Unlike ordinary retyping, the explicit ChatOutput migration keeps
                            # a saved string and its literal/global source mode.
                            for saved_key in ("value", "load_from_db"):
                                if saved_key in saved_field:
                                    replacement[saved_key] = copy.deepcopy(saved_field[saved_key])
                            # Older flows lack the class identity cleanEdges uses to migrate
                            # the saved str handle when this upgraded flow opens in the editor.
                            node_info = node["data"]["node"]
                            node_info["metadata"] = {
                                **(node_info.get("metadata") or {}),
                                "component_class_name": "ChatOutput",
                            }
                        flow_template[key] = replacement
                    # Every saved output still exists on a safe node, so take the registry's
                    # outputs, as the editor's update does: an added output reaches the node. A
                    # tool-mode node keeps its toolset output.
                    node_info = node["data"]["node"]
                    saved_outputs = node_info.get("outputs") or []
                    if entry.get("outputs") is not None and not _node_is_in_tool_mode(saved_outputs):
                        node_info["outputs"] = _updated_outputs(entry["outputs"], saved_outputs)
                    count += 1
                    updated_ids.add(flow_node_id(node))
        node_info = node.get("data", {}).get("node", {})
        nested_flow = node_info.get("flow", {}).get("data", {})
        nested = nested_flow.get("nodes")
        if nested:
            effective_nodes = [node_with_group_values(child, node_info.get("template", {})) for child in nested]
            nested_count, child_ids = _apply_to_nodes(effective_nodes, safe_ids, registry)
            if nested_count:
                nested_flow["nodes"] = effective_nodes
                _update_group_inputs(node_info, effective_nodes, child_ids)
                updated_ids.add(flow_node_id(node))
                count += nested_count
    return count, updated_ids


def _update_group_inputs(node_info: dict, children: list[dict], updated_ids: set[str]) -> None:
    """Keep exposed contracts in sync so ungrouping cannot restore an outdated field type."""
    children_by_id = {flow_node_id(child): child for child in children}
    for name, field_data in node_info.get("template", {}).items():
        if not isinstance(field_data, dict) or not isinstance(proxy := field_data.get("proxy"), dict):
            continue
        child_id = proxy.get("id")
        if child_id not in updated_ids:
            continue
        template = children_by_id[child_id].get("data", {}).get("node", {}).get("template", {})
        child_field = template.get(proxy.get("field"))
        if not isinstance(child_field, dict):
            continue
        replacement = copy.deepcopy(child_field)
        # These properties belong to the group's exposed field, rather than its child.
        for key in ("proxy", "name", "display_name", "show", "advanced"):
            if key in field_data:
                replacement[key] = copy.deepcopy(field_data[key])
        node_info["template"][name] = replacement


def _updated_outputs(registry_outputs: list[dict], saved_outputs: list[dict]) -> list[dict]:
    """Return the registry's outputs with each saved output's ``hidden`` flag, ``options`` and picked type.

    The picked type (``selected``) is kept when the output offers it exactly; otherwise when the output
    offers it under its other name (``Data`` saved, ``JSON`` declared), written in the output's spelling.
    A saved output with no picked type (or one that is not a string) and a single type counts that type
    as its pick. Any other output takes the registry's pick.
    """
    saved = {output.get("name"): output for output in saved_outputs}
    outputs = copy.deepcopy(registry_outputs)
    for output in outputs:
        old = saved.get(output.get("name"))
        if old is None:
            continue
        if "hidden" in old:
            output["hidden"] = old["hidden"]
        if "options" in old:
            output["options"] = old["options"]
        picked = old.get("selected")
        if not isinstance(picked, str):
            saved_types = old.get("types")
            picked = saved_types[0] if isinstance(saved_types, list) and len(saved_types) == 1 else None
        if not isinstance(picked, str):
            continue
        types = output.get("types") or []
        same_type = [t for t in types if _canonical_types([t]) == _canonical_types([picked])]
        if picked in types:
            output["selected"] = picked
        elif same_type:
            output["selected"] = same_type[0]
    return outputs
