"""Component operations: add, remove, configure, list components in flows.

Pure functions that operate on flow dicts. The component registry is passed
as a parameter (dict mapping component_type -> template_dict), not loaded
from global state.

All functions are pure — no I/O, no network, no global state.
"""

from __future__ import annotations

import copy
import json
import secrets
import string
from typing import Any

import yaml

from lfx.graph.flow_builder._utils import node_id as _node_id

# Canvas type for user-authored code components. The frontend resolves this in
# its global template list and exempts it from the "Update available" check
# (componentsToIgnoreUpdate). User overlay entries are keyed by class name in
# the registry so the agent can reference them, but their canvas node must wear
# this type or the frontend flags them as a missing/outdated component.
_CUSTOM_COMPONENT_TYPE = "CustomComponent"


def _generate_id(component_type: str) -> str:
    """Generate a component ID like 'ChatInput-a1B2c'."""
    suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(5))
    return f"{component_type}-{suffix}"


def _normalize_outputs(node_data: dict) -> None:
    """Backfill required Output fields the bundled registry sometimes omits.

    The local registry index (``_assets/component_index.json``) was built from
    component definitions that didn't always serialize every Output field.
    Downstream consumers — the canvas serializer, the ``/custom_component/update``
    endpoint, the LFX dataclass deserializer — expect the full 13-field Output
    shape (see ``lfx.template.field.base.Output``). Partial entries crash with
    ``string indices must be integers, not 'str'`` when a serializer tries to
    walk what it thinks is a dict but the deserializer left as a string.

    Fills the missing fields with the safe defaults real saved outputs use, so
    flows built via ``build_flow_from_spec`` load on the canvas without the
    "Error while updating the Component" toast.

    Idempotent.
    """
    outputs = node_data.get("outputs")
    if not isinstance(outputs, list):
        return
    for output in outputs:
        if not isinstance(output, dict):
            continue
        output.setdefault("hidden", False)
        output.setdefault("options", None)
        output.setdefault("required_inputs", None)


def _make_node(
    component_type: str,
    registry: dict[str, dict],
    component_id: str | None = None,
) -> dict:
    """Create a full node structure from the component registry.

    Args:
        component_type: The type name (e.g. "ChatInput").
        registry: Mapping of component_type -> template dict.
        component_id: Optional explicit ID; auto-generated if None.
    """
    cid = component_id or _generate_id(component_type)

    if component_type not in registry:
        available = ", ".join(sorted(registry.keys())[:20])
        msg = f"Unknown component: {component_type}. Available: {available}..."
        raise ValueError(msg)

    node_data = copy.deepcopy(registry[component_type])
    _normalize_outputs(node_data)

    # User-overlay (assistant-generated) entries are tagged ``custom``. Strip
    # the internal marker and label the canvas node as CustomComponent so the
    # frontend treats it like any user-authored component (no spurious
    # "Update available" badge). Built-ins keep their own type.
    is_custom = bool(node_data.pop("custom", False))
    node_type = _CUSTOM_COMPONENT_TYPE if is_custom else component_type

    return {
        "id": cid,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "selected": False,
        "data": {
            "id": cid,
            "type": node_type,
            "node": node_data,
            "showNode": True,
        },
    }


def add_component(
    flow: dict,
    component_type: str,
    registry: dict[str, dict],
    component_id: str | None = None,
) -> dict:
    """Add a component to a flow with its full template from the registry.

    Returns dict with 'id' and 'display_name'.
    """
    node = _make_node(component_type, registry, component_id=component_id)
    flow["data"]["nodes"].append(node)
    return {"id": node["id"], "display_name": node["data"]["node"].get("display_name", component_type)}


def remove_component(flow: dict, component_id: str) -> None:
    """Remove a component and all its connections from a flow."""
    nodes = flow["data"]["nodes"]
    original_count = len(nodes)
    flow["data"]["nodes"] = [n for n in nodes if _node_id(n) != component_id]
    if len(flow["data"]["nodes"]) == original_count:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    edges = flow["data"]["edges"]
    flow["data"]["edges"] = [e for e in edges if e.get("source") != component_id and e.get("target") != component_id]


def _parse_serialized_model_text(text: str) -> dict | list | None:
    """Try JSON then YAML; return ``None`` when the input is a bare name.

    Only fires on text that looks structured (starts with ``{``, ``[``, or
    ``- ``, or contains an inline ``key: value`` pair) so a bare model name
    like ``"gpt-4o"`` is never silently transformed.
    """
    stripped = (text or "").strip()
    if not stripped:
        return None
    looks_structured = stripped.startswith(("{", "[", "- ")) or (": " in stripped and "\n" in stripped)
    if not looks_structured:
        return None
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, (dict, list)):
            return parsed
    except json.JSONDecodeError:
        pass
    try:
        parsed = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def _coerce_single_model_entry(item: Any) -> Any:
    """Unwrap a nested serialized spec stuffed into ``item['name']``.

    Pattern observed in QA: ``[{"name": "[{...JSON spec...}]", "provider":
    "Unknown"}]``. The outer wrapper is preserved by the catalog fallback,
    but the real provider/name is buried in the inner name string.
    """
    if not isinstance(item, dict):
        return item
    name = item.get("name")
    if not isinstance(name, str):
        return item
    parsed = _parse_serialized_model_text(name)
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    if isinstance(parsed, dict):
        return parsed
    return item


def _coerce_model_value(value: Any) -> Any:
    """Normalize a model-field value to canonical ``list[dict]``.

    Accepts:
      - serialized JSON / YAML string of a list or dict
      - already-canonical ``list[dict]`` (each entry still checked for a
        nested serialized spec in ``name``)
      - a bare name string (left untouched so the catalog path runs)
    """
    if isinstance(value, list):
        return [_coerce_single_model_entry(item) for item in value]
    if isinstance(value, dict):
        return [_coerce_single_model_entry(value)]
    if isinstance(value, str):
        parsed = _parse_serialized_model_text(value)
        if isinstance(parsed, dict):
            return [_coerce_single_model_entry(parsed)]
        if isinstance(parsed, list):
            return [_coerce_single_model_entry(item) for item in parsed]
    return value


def configure_component(
    flow: dict,
    component_id: str,
    params: dict[str, Any],
) -> None:
    """Set parameters on a component (pure version — no server calls).

    Model-typed fields (``template[field].type == "model"``) accept the
    canonical ``[{"provider": X, "name": Y}]`` shape. Some flow-builder
    callers (the agent's ``BuildFlowFromSpec`` and ``ConfigureComponent``
    tools) sometimes emit the spec as a JSON or YAML *string* instead.
    Without normalization, that raw string lands in
    ``template['model'].value``, the catalog falls back to
    ``provider="Unknown"``, and ``get_llm`` raises ``ValueError: missing
    a provider``. Normalize at this single choke point so every caller
    path is covered. ``params`` is mutated in place so post-configure
    helpers (e.g. ``_mirror_model_value_into_options``) read the
    canonical value.
    """
    node = _find_node(flow, component_id)
    if node is None:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    template = node["data"].setdefault("node", {}).setdefault("template", {})
    for key, value in params.items():
        if key not in template:
            available = [k for k in template if isinstance(template[k], dict)]
            msg = f"Unknown parameter '{key}' on component '{component_id}'. Available: {available}"
            raise ValueError(msg)
        if not isinstance(template[key], dict):
            # Reserved non-field entries (e.g. "_type", metadata strings) are not
            # configurable; wrapping them would corrupt the node. Reject instead.
            available = [k for k in template if isinstance(template[k], dict)]
            msg = (
                f"Parameter '{key}' on component '{component_id}' is not a configurable "
                f"field (reserved template entry). Available: {available}"
            )
            # Why: this function's contract raises ValueError for every config
            # error (see sibling check + test_configure_unknown_field_raises);
            # callers catch ValueError. TypeError would break that contract.
            raise ValueError(msg)  # noqa: TRY004
        if template[key].get("type") == "model":
            coerced = _coerce_model_value(value)
            params[key] = coerced
            template[key]["value"] = coerced
        else:
            template[key]["value"] = value


def get_component(flow: dict, component_id: str) -> dict:
    """Get information about a component in a flow."""
    node = _find_node(flow, component_id)
    if node is None:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    node_data = node.get("data", {})
    node_config = node_data.get("node", {})
    template = node_config.get("template", {})

    params = {}
    for key, field in template.items():
        if isinstance(field, dict):
            params[key] = field.get("value")

    return {
        "id": _node_id(node),
        "display_name": node_config.get("display_name", node_data.get("type", "")),
        "type": node_data.get("type", ""),
        "params": params,
        "outputs": node_config.get("outputs", []),
    }


def list_components(flow: dict) -> list[dict]:
    """List all components in a flow."""
    results = []
    for node in flow.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        node_config = node_data.get("node", {})
        results.append(
            {
                "id": _node_id(node),
                "display_name": node_config.get("display_name", node_data.get("type", "")),
                "type": node_data.get("type", ""),
            }
        )
    return results


def needs_server_update(template: dict, field: str) -> bool:
    """Check if setting a field requires server-side template regeneration.

    The frontend triggers /custom_component/update on value change only when
    the field has real_time_refresh=True. tool_mode is handled separately.
    """
    if field == "tool_mode":
        return True
    field_def = template.get(field, {})
    if not isinstance(field_def, dict):
        return False
    return bool(field_def.get("real_time_refresh"))


def _find_node(flow: dict, component_id: str) -> dict | None:
    """Find a node by component ID."""
    for node in flow.get("data", {}).get("nodes", []):
        if _node_id(node) == component_id:
            return node
    return None
