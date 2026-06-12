"""Durable checkpoint data model for HITL graph suspend/resume (LE-1440).

Every field must survive a JSON round-trip (the durable store persists
checkpoints as JSON), including the set-typed execution-state fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

_WIRE_KIND = "__lfx_ser__"


class VertexCheckpointData(BaseModel):
    vertex_id: str
    built: bool = False
    results: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    built_object: Any = None
    built_result: Any = None


class GraphCheckpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: uuid4().hex)
    run_id: str
    flow_id: str | None = None
    session_id: str | None = None
    job_id: str | None = None
    flow_payload: dict[str, Any] = Field(default_factory=dict)
    run_map: dict[str, list[str]] = Field(default_factory=dict)
    run_predecessors: dict[str, list[str]] = Field(default_factory=dict)
    vertices_to_run: set[str] = Field(default_factory=set)
    vertices_being_run: set[str] = Field(default_factory=set)
    ran_at_least_once: set[str] = Field(default_factory=set)
    run_queue: list[str] = Field(default_factory=list)
    call_order: list[str] = Field(default_factory=list)
    vertices_layers: list[list[str]] = Field(default_factory=list)
    first_layer: list[str] = Field(default_factory=list)
    inactivated_vertices: set[str] = Field(default_factory=set)
    activated_vertices: list[str] = Field(default_factory=list)
    vertex_results: dict[str, VertexCheckpointData] = Field(default_factory=dict)
    pause_context: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


def serialize_value(value: Any) -> dict[str, Any] | None:
    """Encode a built value into a JSON-safe tagged envelope.

    Opaque objects (no faithful JSON form) degrade to None rather than raising:
    a checkpoint must still be writable when one vertex holds e.g. a client
    handle, and resume re-derives such objects from the rebuilt component.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return {_WIRE_KIND: "raw", "value": value}
    if isinstance(value, BaseModel):
        return {
            _WIRE_KIND: "model",
            "module": type(value).__module__,
            "name": type(value).__qualname__,
            "value": value.model_dump(mode="json"),
        }
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            return None
        return {_WIRE_KIND: "dict", "value": {k: serialize_value(v) for k, v in value.items()}}
    if isinstance(value, (list, tuple)):
        return {_WIRE_KIND: "list", "value": [serialize_value(v) for v in value]}
    return None


def deserialize_value(wire: dict[str, Any] | None) -> Any:
    if wire is None:
        return None
    kind = wire.get(_WIRE_KIND)
    payload = wire.get("value")
    if kind == "raw":
        return payload
    if kind == "dict":
        return {k: deserialize_value(v) for k, v in (payload or {}).items()}
    if kind == "list":
        return [deserialize_value(v) for v in (payload or [])]
    if kind == "model":
        return _restore_model(wire["module"], wire["name"], payload)
    msg = f"Unknown checkpoint wire kind: {kind!r}"
    raise TypeError(msg)


def _restore_model(module_name: str, class_name: str, payload: Any) -> Any:
    # Why: the module path is data read back from storage — importing arbitrary modules from it would be injection.
    if not module_name.startswith("lfx."):
        msg = f"Refusing to restore checkpoint model from non-lfx module {module_name!r}"
        raise TypeError(msg)
    obj: Any = import_module(module_name)
    for part in class_name.split("."):
        obj = getattr(obj, part)
    if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
        msg = f"{module_name}.{class_name} is not a pydantic model"
        raise TypeError(msg)
    return obj.model_validate(payload)
