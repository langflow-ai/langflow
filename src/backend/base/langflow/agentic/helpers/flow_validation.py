"""Compact flow validation against the live Langflow component registry.

Validates a compact flow JSON dict before it is expanded into full ReactFlow
format. Provides 7 checks ranging from schema correctness to type compatibility,
with auto-correction for close component/field name matches.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowValidationResult:
    """Result of compact flow validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    compact_data: dict = field(default_factory=dict)  # possibly auto-corrected


def _get_flat_components(all_types_dict: dict[str, Any]) -> dict[str, Any]:
    """Flatten the component types dict for easy lookup by component name.

    Reuses the same logic as expand_flow._get_flat_components so that
    validation and expansion use identical component lookup semantics.
    """
    return {
        comp_name: comp_data
        for components in all_types_dict.values()
        if isinstance(components, dict)
        for comp_name, comp_data in components.items()
    }


def _closest_match(name: str, candidates: list[str], n: int = 1, cutoff: float = 0.6) -> str | None:
    """Return the closest matching candidate name, or None if no good match."""
    matches = difflib.get_close_matches(name, candidates, n=n, cutoff=cutoff)
    return matches[0] if matches else None


def _get_output_names(comp_data: dict[str, Any]) -> list[str]:
    """Get output names from component data."""
    outputs = comp_data.get("outputs", [])
    return [o.get("name", "") for o in outputs if isinstance(o, dict) and o.get("name")]


def _get_input_names(comp_data: dict[str, Any]) -> list[str]:
    """Get template field names from component data."""
    template = comp_data.get("template", {})
    return [k for k in template if isinstance(template.get(k), dict)]


def _get_output_types(comp_data: dict[str, Any], output_name: str) -> list[str]:
    """Get output types for a named output."""
    for output in comp_data.get("outputs", []):
        if isinstance(output, dict) and output.get("name") == output_name:
            return output.get("types", [])
    return []


def _get_input_types(comp_data: dict[str, Any], input_name: str) -> list[str]:
    """Get accepted input types for a named template field."""
    template = comp_data.get("template", {})
    field_data = template.get(input_name, {})
    if isinstance(field_data, dict):
        types = field_data.get("input_types", [])
        if not types:
            types = [field_data.get("type", "str")]
        return types
    return []


async def validate_compact_flow(
    compact_data: dict,
    all_types_dict: dict[str, Any] | None = None,
    settings_service: Any | None = None,
) -> FlowValidationResult:
    """Validate a compact flow dict against the live component registry.

    Performs 7 checks:
    1. Schema: verifies nodes/edges structure via CompactFlowData parsing
    2. Component existence: every node.type must be in the registry
    3. Node ID uniqueness: no duplicate node IDs
    4. Edge endpoint validity: edge source/target reference existing node IDs
    5. Output name validity: edge.source_output exists on source component
    6. Input name validity: edge.target_input exists on target component
    7. Type compatibility: output types overlap with input types

    Auto-corrects close name matches (edit distance ≤ 2) for components and
    field names, adding warnings instead of errors when a correction was applied.

    Args:
        compact_data: Raw compact flow dict (nodes + edges).
        all_types_dict: Component registry. Fetched automatically if None.
        settings_service: Settings service for registry access. Auto-detected if None.

    Returns:
        FlowValidationResult with is_valid flag, errors, warnings, and
        (possibly auto-corrected) compact_data.
    """
    from langflow.processing.expand_flow import CompactFlowData

    errors: list[str] = []
    warnings: list[str] = []

    # Fetch registry if not provided
    if all_types_dict is None:
        from langflow.agentic.helpers.component_catalog import get_all_types_dict

        all_types_dict = await get_all_types_dict(settings_service)

    flat_components = _get_flat_components(all_types_dict)
    all_comp_names = list(flat_components.keys())

    # Work on a mutable copy for auto-correction
    import copy

    data = copy.deepcopy(compact_data)

    # --- Check 1: Schema validation ---
    try:
        flow = CompactFlowData(**data)
    except Exception as exc:  # noqa: BLE001
        return FlowValidationResult(
            is_valid=False,
            errors=[f"Schema error: {exc}"],
            compact_data=data,
        )

    # Build a mutable node list for corrections
    nodes = [n.model_dump() for n in flow.nodes]
    edges = [e.model_dump() for e in flow.edges]

    # --- Check 2: Component existence + auto-correct ---
    for node in nodes:
        comp_type = node["type"]
        if comp_type not in flat_components:
            suggestion = _closest_match(comp_type, all_comp_names)
            if suggestion:
                warnings.append(f"Component '{comp_type}' not found — auto-corrected to '{suggestion}'.")
                node["type"] = suggestion
            else:
                errors.append(
                    f"Component type '{comp_type}' not found in registry. Check the available components list."
                )

    # Bail early if unknown components remain (can't validate edges without templates)
    if errors:
        return FlowValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            compact_data={**data, "nodes": nodes, "edges": edges},
        )

    # --- Check 3: Node ID uniqueness ---
    node_ids = [n["id"] for n in nodes]
    seen: set[str] = set()
    for nid in node_ids:
        if nid in seen:
            errors.append(f"Duplicate node ID: '{nid}'.")
        seen.add(nid)

    node_id_set = set(node_ids)

    # --- Checks 4-7: Edge validation ---
    for edge in edges:
        src_id = edge["source"]
        tgt_id = edge["target"]
        src_output = edge["source_output"]
        tgt_input = edge["target_input"]

        # Check 4: Edge endpoint validity
        if src_id not in node_id_set:
            errors.append(f"Edge references unknown source node '{src_id}'.")
            continue
        if tgt_id not in node_id_set:
            errors.append(f"Edge references unknown target node '{tgt_id}'.")
            continue

        # Get component data for source and target
        src_node = next(n for n in nodes if n["id"] == src_id)
        tgt_node = next(n for n in nodes if n["id"] == tgt_id)
        src_comp = flat_components.get(src_node["type"], {})
        tgt_comp = flat_components.get(tgt_node["type"], {})

        # Check 5: Output name validity + auto-correct
        src_outputs = _get_output_names(src_comp)
        if src_outputs and src_output not in src_outputs:
            suggestion = _closest_match(src_output, src_outputs, cutoff=0.4)
            if suggestion:
                warnings.append(
                    f"Output '{src_output}' not found on '{src_node['type']}' — auto-corrected to '{suggestion}'."
                )
                edge["source_output"] = suggestion
                src_output = suggestion
            else:
                warnings.append(
                    f"Output '{src_output}' not found on '{src_node['type']}'. Available: {src_outputs or ['(none)']}"
                )

        # Check 6: Input name validity + auto-correct
        tgt_inputs = _get_input_names(tgt_comp)
        if tgt_inputs and tgt_input not in tgt_inputs:
            suggestion = _closest_match(tgt_input, tgt_inputs, cutoff=0.4)
            if suggestion:
                warnings.append(
                    f"Input '{tgt_input}' not found on '{tgt_node['type']}' — auto-corrected to '{suggestion}'."
                )
                edge["target_input"] = suggestion
                tgt_input = suggestion
            else:
                warnings.append(
                    f"Input '{tgt_input}' not found on '{tgt_node['type']}'. Available: {tgt_inputs or ['(none)']}"
                )

        # Check 7: Type compatibility (warning only)
        src_types = set(_get_output_types(src_comp, src_output))
        tgt_types = set(_get_input_types(tgt_comp, tgt_input))
        if src_types and tgt_types and not src_types.intersection(tgt_types):
            warnings.append(
                f"Type mismatch on edge {src_id}→{tgt_id}: "
                f"source outputs {sorted(src_types)}, target accepts {sorted(tgt_types)}."
            )

    corrected = {**data, "nodes": nodes, "edges": edges}
    return FlowValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        compact_data=corrected,
    )
