"""Flow operation schemas for collaborative editing."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lfx.services.flow_operations.exceptions import FlowOperationValidationError


class FlowOperationActorDelegate(StrEnum):
    """Who performed an accepted operation batch."""

    SELF = "self"
    AGENT = "agent"


class AddNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_nodes"]
    nodes: list[dict[str, Any]]


class UpdateNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_nodes"]
    nodes: list[dict[str, Any]]


class DeleteNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delete_nodes"]
    ids: list[str]


class AddEdgesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_edges"]
    edges: list[dict[str, Any]]


class DeleteEdgesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delete_edges"]
    ids: list[str]


class UpdateMetadataOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_metadata"]
    fields: dict[str, Any] = Field(default_factory=dict)
    delete_keys: list[str] = Field(default_factory=list)


FlowOperation = AddNodesOp | UpdateNodesOp | DeleteNodesOp | AddEdgesOp | DeleteEdgesOp | UpdateMetadataOp

GRAPH_COLLECTION_KEYS = frozenset({"nodes", "edges"})


def normalize_requested_ops(operations: list[FlowOperation]) -> list[FlowOperation]:
    """Return a shallow copy of parsed operations, preserving order."""
    return list(operations)


def parse_flow_operations(operations: list[dict[str, Any]]) -> list[FlowOperation]:
    """Parse raw operation payloads at API/transport boundaries."""
    if not isinstance(operations, list):
        msg = "operations must be a list"
        raise FlowOperationValidationError(msg)
    return [parse_flow_operation(operation) for operation in operations]


def parse_flow_operation(operation: dict[str, Any]) -> FlowOperation:
    """Parse a single raw operation payload at API/transport boundaries."""
    if not isinstance(operation, dict):
        msg = "operation must be a dict"
        raise FlowOperationValidationError(msg)

    operation_type = operation.get("type")
    try:
        if operation_type == "add_nodes":
            return AddNodesOp.model_validate(operation)
        if operation_type == "update_nodes":
            return UpdateNodesOp.model_validate(operation)
        if operation_type == "delete_nodes":
            return DeleteNodesOp.model_validate(operation)
        if operation_type == "add_edges":
            return AddEdgesOp.model_validate(operation)
        if operation_type == "delete_edges":
            return DeleteEdgesOp.model_validate(operation)
        if operation_type == "update_metadata":
            return UpdateMetadataOp.model_validate(operation)
    except ValidationError as exc:
        raise FlowOperationValidationError(str(exc)) from exc

    msg = f"Unsupported operation type: {operation_type!r}"
    raise FlowOperationValidationError(msg)


def coalesce_delete_ids(ids: list[str]) -> list[str]:
    """Preserve first-seen order while removing duplicate delete IDs."""
    return list(dict.fromkeys(ids))
