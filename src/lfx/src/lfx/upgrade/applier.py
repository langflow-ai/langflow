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
) -> dict | tuple[dict, int]:
    """Return a deep copy of flow_data with safe node codes updated.

    Args:
        flow_data: Parsed flow JSON with a ``nodes`` list.
        all_types_dict: Component registry (same shape as ``check_flow_compatibility``).
        report: Pre-computed CompatibilityReport from ``check_flow_compatibility``.
        return_count: If True, return a (flow, count) tuple where count is the
                      number of nodes that were updated.

    Returns:
        Updated flow dict (deep copy), or (flow, count) if return_count=True.
    """
    safe_ids = {n.node_id for n in report.nodes if n.status == "outdated_safe"}
    if not safe_ids:
        updated = copy.deepcopy(flow_data)
        return (updated, 0) if return_count else updated

    registry = build_registry_lookup(all_types_dict)
    updated = copy.deepcopy(flow_data)
    count = 0

    for node in updated.get("nodes", []):
        node_id = node.get("data", {}).get("id") or node.get("id")
        if node_id not in safe_ids:
            continue
        component_type = node["data"].get("type", "")
        entry = registry.get(component_type)
        if not entry:
            continue
        registry_code_field = entry.get("template", {}).get("code")
        new_code = registry_code_field.get("value") if isinstance(registry_code_field, dict) else None
        if new_code is None:
            continue
        node["data"]["node"]["template"]["code"]["value"] = new_code
        count += 1

    return (updated, count) if return_count else updated
