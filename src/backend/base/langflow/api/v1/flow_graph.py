"""Agent-friendly read endpoints for the flow graph (components + edges).

These endpoints expose a flat, structured view of a flow's nodes and edges so
that AI agents can reason about a flow without parsing the full ReactFlow
payload stored in ``Flow.data``.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import attributes as orm_attributes

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.flows_helpers import _read_flow

router = APIRouter(prefix="/flows", tags=["Flow Graph"])


class ComponentInputSummary(BaseModel):
    name: str
    display_name: str | None = None
    type: str | None = None
    input_types: list[str] = Field(default_factory=list)
    required: bool = False
    advanced: bool = False
    show: bool = True
    value: Any | None = None


class ComponentOutputSummary(BaseModel):
    name: str
    display_name: str | None = None
    method: str | None = None
    types: list[str] = Field(default_factory=list)


class ComponentSummary(BaseModel):
    id: str
    type: str
    display_name: str | None = None
    description: str | None = None
    position: dict[str, float] | None = None
    inputs: list[ComponentInputSummary] = Field(default_factory=list)
    outputs: list[ComponentOutputSummary] = Field(default_factory=list)


class EdgeSummary(BaseModel):
    id: str
    source: str
    target: str
    source_output: str | None = None
    target_input: str | None = None
    source_types: list[str] = Field(default_factory=list)
    target_types: list[str] = Field(default_factory=list)


class AddComponentRequest(BaseModel):
    type: str = Field(description="Component type from the catalog, e.g. 'ChatInput'.")
    component_id: str | None = Field(
        default=None,
        description="Explicit node id; auto-generated as '{type}-{rand5}' if omitted.",
    )
    position: dict[str, float] | None = Field(
        default=None,
        description="Optional {x, y} canvas position; defaults to (0, 0).",
    )


class AddEdgeRequest(BaseModel):
    source: str = Field(description="Source node id.")
    source_output: str = Field(description="Output handle name on the source node.")
    target: str = Field(description="Target node id.")
    target_input: str = Field(description="Input field name on the target node.")


# ReactFlow encodes handle objects inside edge IDs/handle strings using the
# Latin small-ligature "œ" (œ) in place of double quotes. Replace it back
# before json.loads.
_HANDLE_QUOTE_PLACEHOLDER = "œ"


def _parse_handle(handle: Any) -> dict[str, Any]:
    if isinstance(handle, dict):
        return handle
    if isinstance(handle, str) and handle:
        try:
            return json.loads(handle.replace(_HANDLE_QUOTE_PLACEHOLDER, '"'))
        except json.JSONDecodeError:
            return {}
    return {}


def _node_to_summary(node: dict[str, Any]) -> ComponentSummary:
    data = node.get("data") or {}
    node_def = data.get("node") or {}
    template = node_def.get("template") or {}

    inputs: list[ComponentInputSummary] = []
    for field_name, field_def in template.items():
        if field_name == "_type" or not isinstance(field_def, dict):
            continue
        inputs.append(
            ComponentInputSummary(
                name=field_name,
                display_name=field_def.get("display_name"),
                type=field_def.get("type"),
                input_types=field_def.get("input_types") or [],
                required=bool(field_def.get("required", False)),
                advanced=bool(field_def.get("advanced", False)),
                show=bool(field_def.get("show", True)),
                value=field_def.get("value"),
            )
        )

    outputs: list[ComponentOutputSummary] = []
    for out in node_def.get("outputs") or []:
        if not isinstance(out, dict):
            continue
        outputs.append(
            ComponentOutputSummary(
                name=out.get("name", ""),
                display_name=out.get("display_name"),
                method=out.get("method"),
                types=out.get("types") or [],
            )
        )

    return ComponentSummary(
        id=node.get("id", ""),
        type=data.get("type") or "",
        display_name=data.get("display_name") or node_def.get("display_name"),
        description=data.get("description") or node_def.get("description"),
        position=node.get("position"),
        inputs=inputs,
        outputs=outputs,
    )


def _edge_to_summary(edge: dict[str, Any]) -> EdgeSummary:
    edge_data = edge.get("data") or {}
    src_handle = edge_data.get("sourceHandle") or _parse_handle(edge.get("sourceHandle"))
    tgt_handle = edge_data.get("targetHandle") or _parse_handle(edge.get("targetHandle"))

    return EdgeSummary(
        id=edge.get("id", ""),
        source=edge.get("source", ""),
        target=edge.get("target", ""),
        source_output=src_handle.get("name"),
        target_input=tgt_handle.get("fieldName"),
        source_types=src_handle.get("output_types") or [],
        target_types=tgt_handle.get("inputTypes") or [],
    )


@router.get("/{flow_id}/components", response_model=list[ComponentSummary])
async def list_flow_components(
    *,
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """List all components of a flow with their inputs, outputs and types."""
    flow = await _read_flow(session, flow_id, current_user.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    flow_data = flow.data or {}
    nodes = flow_data.get("nodes") or []
    return [_node_to_summary(n) for n in nodes if isinstance(n, dict)]


@router.get("/{flow_id}/edges", response_model=list[EdgeSummary])
async def list_flow_edges(
    *,
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """List all edges of a flow with source/target endpoints and handle types."""
    flow = await _read_flow(session, flow_id, current_user.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    flow_data = flow.data or {}
    edges = flow_data.get("edges") or []
    return [_edge_to_summary(e) for e in edges if isinstance(e, dict)]


async def _load_component_registry() -> dict[str, dict[str, Any]]:
    """Flatten the cached all-types catalog into {component_type: template_dict}.

    Mirrors the shape that ``lfx.graph.flow_builder`` helpers expect.
    """
    from langflow.interface.components import get_and_cache_all_types_dict
    from langflow.services.deps import get_settings_service

    all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())
    registry: dict[str, dict[str, Any]] = {}
    for category, items in (all_types or {}).items():
        if not isinstance(items, dict):
            continue
        for name, comp_data in items.items():
            if isinstance(comp_data, dict) and "template" in comp_data:
                registry[name] = {**comp_data, "category": category}
    return registry


def _wrap_flow_data(flow_data: dict[str, Any] | None) -> dict[str, Any]:
    """Wrap a Flow.data dict into the shape that flow_builder helpers expect.

    The helpers operate on ``flow["data"]["nodes"]`` and ``flow["data"]["edges"]``
    while the DB stores those keys directly on ``Flow.data``. This wrapper also
    guarantees both keys exist so callers can mutate them without checks.
    """
    inner = copy.deepcopy(flow_data) if flow_data else {}
    inner.setdefault("nodes", [])
    inner.setdefault("edges", [])
    return {"data": inner}


async def _persist_flow_data(session, db_flow, new_inner: dict[str, Any]) -> None:
    """Write back mutated flow data and refresh the ORM instance."""
    db_flow.data = new_inner
    # JSON column won't auto-flag dirty when we mutate in place; force the change.
    orm_attributes.flag_modified(db_flow, "data")
    db_flow.updated_at = datetime.now(timezone.utc)
    session.add(db_flow)
    await session.flush()
    await session.refresh(db_flow)


@router.post("/{flow_id}/components", response_model=ComponentSummary, status_code=201)
async def add_flow_component(
    *,
    flow_id: UUID,
    payload: AddComponentRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Append a new component to a flow.

    Looks up the component template from the catalog, instantiates a node, and
    appends it to ``flow.data.nodes``. Use ``GET /api/v1/all`` to discover
    available component types.
    """
    db_flow = await _read_flow(session, flow_id, current_user.id)
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    from lfx.graph.flow_builder.component import add_component as fb_add_component

    registry = await _load_component_registry()
    flow_dict = _wrap_flow_data(db_flow.data)

    try:
        fb_add_component(
            flow_dict,
            payload.type,
            registry,
            component_id=payload.component_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_node = flow_dict["data"]["nodes"][-1]
    if payload.position:
        new_node["position"] = {"x": float(payload.position.get("x", 0)), "y": float(payload.position.get("y", 0))}

    await _persist_flow_data(session, db_flow, flow_dict["data"])
    return _node_to_summary(new_node)


@router.post("/{flow_id}/edges", response_model=EdgeSummary, status_code=201)
async def add_flow_edge(
    *,
    flow_id: UUID,
    payload: AddEdgeRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Connect two components by adding an edge.

    Resolves source/target handle types from the flow and validates that the
    output types are compatible with the input types (raises 400 on mismatch).
    The operation is idempotent: connecting the same pair twice returns the
    existing edge.
    """
    db_flow = await _read_flow(session, flow_id, current_user.id)
    if not db_flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    from lfx.graph.flow_builder.connect import add_connection as fb_add_connection

    flow_dict = _wrap_flow_data(db_flow.data)

    try:
        edge = fb_add_connection(
            flow_dict,
            payload.source,
            payload.source_output,
            payload.target,
            payload.target_input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await _persist_flow_data(session, db_flow, flow_dict["data"])
    return _edge_to_summary(edge)
