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
            if (node_id, name) in connected or model_identity(field.get("value")) is None:
                continue
            yield node, name, field


def model_fields(flow_data: dict[str, Any] | None) -> list[FlowModelField]:
    """Every model picker that holds a selected model, in flow order."""
    found: list[FlowModelField] = []
    for node, name, field in _model_field_entries(flow_data or {}):
        data = node.get("data") or {}
        inner = data.get("node") or {}
        value = field.get("value")
        found.append(
            FlowModelField(
                node_id=str(data.get("id") or node.get("id")),
                component=str(inner.get("display_name") or data.get("type") or ""),
                field=name,
                display_name=str(field.get("display_name") or name),
                model_type=str(field.get("model_type") or DEFAULT_MODEL_TYPE),
                value=value if isinstance(value, list) else [value],
            )
        )
    return found


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
