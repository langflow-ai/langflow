"""Flow operation schemas for collaborative editing."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from lfx.services.flow_operations.exceptions import FlowOperationValidationError


class AddNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_nodes"]
    nodes: list[dict[str, Any]]


NodeFieldPathSegment = str | int
NodeFieldPath = tuple[NodeFieldPathSegment, ...]


class _NodeFieldUpdateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path: NodeFieldPath

    @field_validator("id")
    @classmethod
    def validate_node_id(cls, node_id: str) -> str:
        if not isinstance(node_id, str) or not node_id:
            msg = "update_nodes entry id must be a non-empty string"
            raise ValueError(msg)
        return node_id

    @field_validator("path")
    @classmethod
    def validate_path(cls, path: NodeFieldPath) -> NodeFieldPath:
        if not path:
            msg = "update_nodes entry path must not be empty"
            raise ValueError(msg)
        for segment in path:
            # bool is a subclass of int, but JSON booleans are not valid array indexes here.
            if isinstance(segment, bool) or not isinstance(segment, (str, int)):
                msg = "update_nodes entry path segments must be strings or integers"
                raise TypeError(msg)
        return path


class SetNodeFieldUpdate(_NodeFieldUpdateBase):
    op: Literal["set_field"]
    value: Any


class DeleteNodeFieldUpdate(_NodeFieldUpdateBase):
    op: Literal["delete_field"]


class OverwriteNodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    op: Literal["overwrite_node"]
    node: dict[str, Any]

    @field_validator("id")
    @classmethod
    def validate_node_id(cls, node_id: str) -> str:
        if not isinstance(node_id, str) or not node_id:
            msg = "update_nodes entry id must be a non-empty string"
            raise ValueError(msg)
        return node_id

    @model_validator(mode="after")
    def validate_payload_node_id(self) -> OverwriteNodeUpdate:
        payload_node_id = self.node.get("id")
        if not isinstance(payload_node_id, str) or not payload_node_id:
            msg = "overwrite_node node must have a non-empty string id"
            raise ValueError(msg)
        if payload_node_id != self.id:
            msg = "overwrite_node node id must match update id"
            raise ValueError(msg)
        return self


UpdateNodeEntry = Annotated[
    SetNodeFieldUpdate | DeleteNodeFieldUpdate | OverwriteNodeUpdate,
    Field(discriminator="op"),
]


class UpdateNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_nodes"]
    updates: list[UpdateNodeEntry]


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
