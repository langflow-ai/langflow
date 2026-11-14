"""Find the model pickers of a flow and swap their models for one evaluation run, never in the saved flow."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from langflow.services.evaluations.errors import EvalsValidationError
from langflow.services.evaluations.pricing import model_identity
from langflow.services.evaluations.schemas import FlowModelField, ModelOverride

if TYPE_CHECKING:
    from collections.abc import Iterable

MODEL_FIELD_TYPE = "model"
DEFAULT_MODEL_TYPE = "language"


def _connected_fields(flow_data: dict[str, Any]) -> set[tuple[str, str]]:
    """(node id, field) pairs fed by an edge: their model comes from another component."""
    connected: set[tuple[str, str]] = set()
    for edge in flow_data.get("edges") or []:
        handle = ((edge or {}).get("data") or {}).get("targetHandle") or {}
        target, field = handle.get("id") or (edge or {}).get("target"), handle.get("fieldName")
        if isinstance(target, str) and isinstance(field, str):
            connected.add((target, field))
    return connected


def is_unset(field: dict[str, Any]) -> bool:
    """A required picker saved without a model: the component fails to build until one is chosen."""
    return model_identity(field.get("value")) is None and bool(field.get("required"))


def _model_field_entries(flow_data: dict[str, Any]) -> Iterable[tuple[dict[str, Any], str, dict[str, Any]]]:
    connected = _connected_fields(flow_data)
    for node in flow_data.get("nodes") or []:
        if not isinstance(node, dict) or node.get("type") == "noteNode":
            continue
        node_id = str((node.get("data") or {}).get("id") or node.get("id") or "")
        template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
        for name, field in template.items():
            if not isinstance(field, dict) or field.get("type") != MODEL_FIELD_TYPE:
                continue
            if (node_id, name) in connected:
                continue
            # An empty optional picker is unused; an empty required one is listed so a run can choose its model.
            if model_identity(field.get("value")) is None and not is_unset(field):
                continue
            yield node, name, field


def _component_names(entries: list[tuple[dict[str, Any], str, dict[str, Any]]]) -> dict[str, str]:
    """Each picker node's component name, numbered in flow order when several share it ("Agent (2)")."""
    names: dict[str, str] = {}
    for node, _, _ in entries:
        data = node.get("data") or {}
        node_id = str(data.get("id") or node.get("id"))
        names.setdefault(node_id, str((data.get("node") or {}).get("display_name") or data.get("type") or ""))
    totals: dict[str, int] = {}
    for name in names.values():
        totals[name] = totals.get(name, 0) + 1
    seen: dict[str, int] = {}
    for node_id, name in names.items():
        if totals[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            names[node_id] = f"{name} ({seen[name]})"
    return names


def model_fields(flow_data: dict[str, Any] | None) -> list[FlowModelField]:
    """Every model picker that holds a model, or must and does not, in flow order."""
    entries = list(_model_field_entries(flow_data or {}))
    components = _component_names(entries)
    found: list[FlowModelField] = []
    for node, name, field in entries:
        data = node.get("data") or {}
        node_id = str(data.get("id") or node.get("id"))
        value = field.get("value")
        found.append(
            FlowModelField(
                node_id=node_id,
                component=components[node_id],
                field=name,
                display_name=str(field.get("display_name") or name),
                model_type=str(field.get("model_type") or DEFAULT_MODEL_TYPE),
                value=[] if is_unset(field) else value if isinstance(value, list) else [value],
            )
        )
    return found


def unset_model_fields(flow_data: dict[str, Any] | None) -> list[FlowModelField]:
    """Required pickers still without a model, which would fail every row."""
    return [field for field in model_fields(flow_data) if not field.value]


def require_models(flow_data: dict[str, Any]) -> None:
    """Refuse a run whose flow, after its overrides, still leaves a required picker without a model."""
    unset = unset_model_fields(flow_data)
    if unset:
        names = ", ".join(f"{field.component} ({field.display_name})" for field in unset)
        msg = f"Choose a model under Models for: {names}. The flow has none selected."
        raise EvalsValidationError(msg)


def apply_model_overrides(
    flow_data: dict[str, Any], overrides: Iterable[ModelOverride | dict[str, Any]]
) -> dict[str, Any]:
    """A copy of the flow with each override's model set; an override for a field the flow lacks is refused."""
    parsed: list[ModelOverride] = [
        item if isinstance(item, ModelOverride) else ModelOverride.model_validate(item) for item in overrides
    ]
    if not parsed:
        return flow_data
    patched = copy.deepcopy(flow_data)
    fields = {
        (str((node.get("data") or {}).get("id") or node.get("id")), name): field
        for node, name, field in _model_field_entries(patched)
    }
    for override in parsed:
        field = fields.get((override.node_id, override.field))
        if field is None:
            msg = f"The model field {override.field} of component {override.node_id} is not in this flow version."
            raise EvalsValidationError(msg)
        field["value"] = copy.deepcopy(override.value)
    return patched
