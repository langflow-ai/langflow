"""Apply safe upgrades to a flow dict.

Returns a deep copy of the flow with safe-upgradeable node codes replaced
by the current registry code. Breaking and blocked nodes are left unchanged.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from lfx.upgrade.checker import CompatibilityReport, build_registry_lookup


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
    count = _apply_to_nodes(updated.get("nodes", []), safe_ids, registry)

    return (updated, count) if return_count else updated


def _apply_to_nodes(nodes: list[dict], safe_ids: set[str], registry: dict[str, dict]) -> int:
    """Walk top-level nodes and (one level of) nested flow nodes, applying safe upgrades.

    Mirrors check_flow_compatibility's recursion into ``node.data.node.flow.data.nodes``
    so safe-upgradeable nodes inside grouped components are written, not silently skipped.
    """
    count = 0
    for node in nodes:
        node_id = node.get("data", {}).get("id") or node.get("id")
        if node_id in safe_ids:
            component_type = node.get("data", {}).get("type", "")
            entry = registry.get(component_type)
            if entry:
                registry_code_field = entry.get("template", {}).get("code")
                new_code = registry_code_field.get("value") if isinstance(registry_code_field, dict) else None
                if new_code is not None:
                    node["data"]["node"]["template"]["code"]["value"] = new_code
                    count += 1
        nested = node.get("data", {}).get("node", {}).get("flow", {}).get("data", {}).get("nodes")
        if nested:
            count += _apply_to_nodes(nested, safe_ids, registry)
    return count
