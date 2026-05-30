"""Flow operation schemas for collaborative editing."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


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


FlowOperation = Annotated[
    AddNodesOp | UpdateNodesOp | DeleteNodesOp | AddEdgesOp | DeleteEdgesOp | UpdateMetadataOp,
    Field(discriminator="type"),
]

_FLOW_OPERATION_ADAPTER = TypeAdapter(FlowOperation)
_FLOW_OPERATIONS_LIST_ADAPTER = TypeAdapter(list[FlowOperation])

GRAPH_COLLECTION_KEYS = frozenset({"nodes", "edges"})


def normalize_requested_ops(operations: list[FlowOperation]) -> list[FlowOperation]:
    """Return a shallow copy of parsed operations, preserving order."""
    return list(operations)


def parse_flow_operations(operations: list[dict[str, Any]]) -> list[FlowOperation]:
    """Parse raw operation payloads at API/transport boundaries."""
    return _FLOW_OPERATIONS_LIST_ADAPTER.validate_python(operations)


def parse_flow_operation(operation: dict[str, Any]) -> FlowOperation:
    """Parse a single raw operation payload at API/transport boundaries."""
    return _FLOW_OPERATION_ADAPTER.validate_python(operation)


def coalesce_delete_ids(ids: list[str]) -> list[str]:
    """Preserve first-seen order while removing duplicate delete IDs."""
    return list(dict.fromkeys(ids))
