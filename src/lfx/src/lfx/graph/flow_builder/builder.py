"""Build a complete flow from a text spec using the local component registry.

The component registry is loaded from a bundled index file and cached
at module level. No network access or running server required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lfx.graph.flow_builder.component import add_component, configure_component
from lfx.graph.flow_builder.connect import add_connection
from lfx.graph.flow_builder.flow import empty_flow
from lfx.graph.flow_builder.layout import layout_flow
from lfx.graph.flow_builder.spec import parse_flow_spec, validate_spec_references
from lfx.log.logger import logger

_INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "_assets" / "component_index.json"
_registry_cache: dict[str, dict] | None = None


def load_local_registry() -> dict[str, dict]:
    """Load the component registry from the bundled index file.

    Returns a flat dict: {component_type: template_dict}.
    Results are cached after the first call.

    Raises:
        RuntimeError: If the index file is missing, corrupt, or empty.
    """
    global _registry_cache  # noqa: PLW0603
    if _registry_cache is not None:
        return _registry_cache

    try:
        with _INDEX_PATH.open() as f:
            data = json.load(f)
    except FileNotFoundError:
        msg = f"Component registry not found at {_INDEX_PATH}. The lfx package may be installed incorrectly."
        raise RuntimeError(msg) from None
    except (json.JSONDecodeError, OSError) as e:
        msg = f"Failed to load component registry from {_INDEX_PATH}: {e}"
        raise RuntimeError(msg) from e

    registry: dict[str, dict] = {}
    for cat in data.get("entries", []):
        if isinstance(cat, list) and len(cat) > 1 and isinstance(cat[1], dict):
            category_name = cat[0] if isinstance(cat[0], str) else ""
            for name, comp_data in cat[1].items():
                if isinstance(comp_data, dict) and "template" in comp_data:
                    registry[name] = {**comp_data, "category": category_name}

    if not registry:
        msg = f"Component registry at {_INDEX_PATH} contains no valid components."
        raise RuntimeError(msg)

    logger.debug("Loaded %d components from local registry", len(registry))
    _registry_cache = registry
    return registry


def build_flow_from_spec(spec: str) -> dict[str, Any]:
    """Build a flow dict from a text spec. Returns the flow or errors.

    On success: {"flow": <flow_dict>, "name": str, "node_count": int, "edge_count": int}
    On failure: {"error": str, "details": str}
    """
    registry = load_local_registry()

    try:
        parsed = parse_flow_spec(spec)
    except ValueError as e:
        return {"error": "Invalid spec", "details": str(e)}

    # Validate that all component types exist in the registry
    unknown = [n["type"] for n in parsed["nodes"] if n["type"] not in registry]
    if unknown:
        return {
            "error": f"Unknown component types: {unknown}",
            "details": f"Available types (sample): {sorted(registry.keys())[:30]}",
        }

    # Validate node references in edges and config
    try:
        validate_spec_references(parsed)
    except ValueError as e:
        return {"error": str(e), "details": str(e)}

    # Build the flow
    flow = empty_flow(
        name=parsed.get("name", "Untitled Flow"),
        description=parsed.get("description", ""),
    )

    id_map: dict[str, str] = {}

    # Add components
    for node in parsed["nodes"]:
        try:
            result = add_component(flow, node["type"], registry)
        except (ValueError, KeyError) as e:
            return {"error": f"Failed to add component '{node['type']}' (node '{node['id']}')", "details": str(e)}
        id_map[node["id"]] = result["id"]

    # Apply config
    for spec_id, params in parsed.get("config", {}).items():
        try:
            configure_component(flow, id_map[spec_id], params)
        except (ValueError, KeyError) as e:
            return {"error": f"Failed to configure node '{spec_id}'", "details": str(e)}

    # Connect edges
    for edge in parsed["edges"]:
        src_out = f"{edge['source_id']}.{edge['source_output']}"
        tgt_in = f"{edge['target_id']}.{edge['target_input']}"
        try:
            add_connection(
                flow,
                id_map[edge["source_id"]],
                edge["source_output"],
                id_map[edge["target_id"]],
                edge["target_input"],
            )
        except (ValueError, KeyError) as e:
            return {"error": f"Failed to connect {src_out} -> {tgt_in}", "details": str(e)}

    layout_flow(flow)

    flow["name"] = parsed.get("name", "Untitled Flow")
    flow["description"] = parsed.get("description", "")

    return {
        "flow": flow,
        "name": flow["name"],
        "node_count": len(flow["data"]["nodes"]),
        "edge_count": len(flow["data"]["edges"]),
        "node_id_map": id_map,
    }
