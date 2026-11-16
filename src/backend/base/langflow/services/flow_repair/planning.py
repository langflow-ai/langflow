"""Recompute safe repairs from trusted templates without executing saved code."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from lfx.graph.graph.utils import process_flow
from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import _canonical_types, build_registry_lookup, check_flow_compatibility, iter_flow_nodes


@dataclass(frozen=True)
class RepairPlan:
    data: dict[str, Any] | None = None
    updated_nodes: int = 0
    reason_codes: list[str] = field(default_factory=list)


def data_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _nodes_by_path(graph: Mapping[str, Any], prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], dict]:
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        msg = "malformed_graph"
        raise TypeError(msg)
    result = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            msg = "malformed_node"
            raise TypeError(msg)
        path = (*prefix, node["id"])
        if path in result:
            msg = "duplicate_node_id"
            raise ValueError(msg)
        result[path] = node
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            msg = "malformed_node"
            raise TypeError(msg)
        info = node_data.get("node", {})
        if not isinstance(info, dict):
            msg = "malformed_node"
            raise TypeError(msg)
        nested = info.get("flow")
        if nested is not None:
            if not isinstance(nested, dict) or not isinstance(nested.get("data"), dict):
                msg = "malformed_group"
                raise TypeError(msg)
            result.update(_nodes_by_path(nested["data"], path))
    if any(not isinstance(edge, dict) for edge in edges):
        msg = "malformed_edge"
        raise TypeError(msg)
    return result


def _preserves_template_state(old_template: object, new_template: object) -> bool:
    if not isinstance(old_template, dict) or not isinstance(new_template, dict):
        return False
    for name, old_field in old_template.items():
        if name == "code" or not isinstance(old_field, dict):
            continue
        new_field = new_template.get(name)
        if not isinstance(new_field, dict):
            return False
        for key in ("value", "load_from_db", "file_path"):
            if key in old_field and old_field[key] != new_field.get(key):
                return False
    return True


def _preserves_code(old_template: object, new_template: object, trusted_source: str | None) -> bool:
    if not isinstance(old_template, dict) or not isinstance(new_template, dict):
        return False
    old_code, new_code = old_template.get("code"), new_template.get("code")
    old_source = old_code.get("value") if isinstance(old_code, dict) else None
    new_source = new_code.get("value") if isinstance(new_code, dict) else None
    return new_source == trusted_source if trusted_source is not None else old_source == new_source


def _preserves_saved_state(
    before: Mapping[str, Any], after: Mapping[str, Any], safe_sources: Mapping[str, str]
) -> bool:
    if before.get("edges") != after.get("edges"):
        return False
    old_nodes, new_nodes = _nodes_by_path(before), _nodes_by_path(after)
    if old_nodes.keys() != new_nodes.keys():
        return False
    # Compare the values the runtime applies, while keeping raw nodes below for
    # the stronger edited-node, topology, and output preservation checks.
    old_templates = {
        (*path, node["id"]): node["data"].get("node", {}).get("template", {})
        for node, _, path in iter_flow_nodes(before["nodes"], before["edges"])
    }
    new_templates = {
        (*path, node["id"]): node["data"].get("node", {}).get("template", {})
        for node, _, path in iter_flow_nodes(after["nodes"], after["edges"])
    }
    for path, old in old_nodes.items():
        new = new_nodes[path]
        old_info, new_info = old["data"].get("node", {}), new["data"].get("node", {})
        if old_info.get("edited") is True and old != new:
            return False
        trusted_source = safe_sources.get(old["id"])
        if not _preserves_code(old_info.get("template", {}), new_info.get("template", {}), trusted_source):
            return False
        if old_info.get("flow") is not None and old_info["flow"]["data"].get("edges") != new_info.get("flow", {}).get(
            "data", {}
        ).get("edges"):
            return False
        old_outputs, new_outputs = old_info.get("outputs", []), new_info.get("outputs", [])
        if not isinstance(old_outputs, list) or not isinstance(new_outputs, list):
            return False
        outputs_by_name = {output.get("name"): output for output in new_outputs if isinstance(output, dict)}
        for output in old_outputs:
            if not isinstance(output, dict) or output.get("name") not in outputs_by_name:
                return False
            replacement = outputs_by_name[output.get("name")]
            for key in ("hidden", "options"):
                if key in output and output[key] != replacement.get(key):
                    return False
            picked = output.get("selected")
            new_pick = replacement.get("selected")
            if isinstance(picked, str) and (
                not isinstance(new_pick, str) or _canonical_types([picked]) != _canonical_types([new_pick])
            ):
                return False
        if not _preserves_template_state(old_templates[path], new_templates[path]):
            return False
        if not _preserves_code(old_templates[path], new_templates[path], trusted_source):
            return False
    # Flattening a saved nested group can differ from the exposed-value
    # projection. A repair must preserve the inputs the current runtime consumes
    # as well. This transformation only copies graph dictionaries; it runs no code.
    old_runtime = _nodes_by_path(process_flow(copy.deepcopy(before)))
    new_runtime = _nodes_by_path(process_flow(copy.deepcopy(after)))
    return old_runtime.keys() == new_runtime.keys() and all(
        _preserves_template_state(
            old["data"].get("node", {}).get("template", {}),
            new_runtime[path]["data"].get("node", {}).get("template", {}),
        )
        and _preserves_code(
            old["data"].get("node", {}).get("template", {}),
            new_runtime[path]["data"].get("node", {}).get("template", {}),
            safe_sources.get(old["id"]),
        )
        for path, old in old_runtime.items()
    )


def plan_flow_repair(data: dict[str, Any], all_types: Mapping[str, Any]) -> RepairPlan:
    """Keep the entire flow unchanged unless every planned change preserves saved state."""
    try:
        nodes = _nodes_by_path(data)
        ids = [node["id"] for node in nodes.values()]
        if len(set(ids)) != len(ids):
            return RepairPlan(reason_codes=["duplicate_node_id"])
        registry = build_registry_lookup(all_types)
        report = check_flow_compatibility(data, all_types, registry=registry)
        unsafe: list[str] = sorted(
            {node.status for node in report.nodes if node.status in {"blocked", "retired", "outdated_breaking"}}
        )
        if unsafe:
            return RepairPlan(reason_codes=unsafe)
        safe_sources = {}
        for node in report.nodes:
            if node.status == "outdated_safe":
                code = registry[node.component_type].get("template", {}).get("code")
                if isinstance(code, dict) and isinstance(code.get("value"), str):
                    safe_sources[node.node_id] = code["value"]
        updated, count = apply_safe_upgrades(data, all_types, report, return_count=True, registry=registry)
        if not _preserves_saved_state(data, updated, safe_sources):
            return RepairPlan(reason_codes=["preservation_failed"])
        if not count:
            reasons = ["customized_nodes_skipped"] if report.has_customized else []
            return RepairPlan(data=copy.deepcopy(data), reason_codes=reasons)
        return RepairPlan(data=updated, updated_nodes=count)
    except (KeyError, TypeError, ValueError, AttributeError):
        return RepairPlan(reason_codes=["malformed_flow"])
