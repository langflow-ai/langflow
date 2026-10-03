"""Flow operation schemas."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from lfx.services.flow_operations.exceptions import FlowOperationValidationError


class AddNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_nodes"]
    nodes: list[dict[str, Any]]


class IdSelector(BaseModel):
    """Selects a table row by its ``_id``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value:
            msg = "an id selector must name a non-empty id"
            raise ValueError(msg)
        return value


class KeySelector(BaseModel):
    """Selects an item of a natural-key list (an output by name, a tool action by tag)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not value:
            msg = "a key selector must name a non-empty key"
            raise ValueError(msg)
        return value


ListSelector = IdSelector | KeySelector
NodeFieldPathSegment = str | IdSelector | KeySelector
NodeFieldPath = tuple[NodeFieldPathSegment, ...]


class ExpectValue(BaseModel):
    """The value a path must hold before a write, compared canonically."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: Any


class ExpectAbsent(BaseModel):
    """A write that requires its path not to exist yet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    absent: Literal[True]


Expectation = ExpectValue | ExpectAbsent


class _NodeFieldUpdateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path: NodeFieldPath
    # What the path must hold before this write. On mismatch the whole batch
    # fails with FlowOperationPreconditionError.
    expect: Expectation | None = None

    @field_validator("id")
    @classmethod
    def validate_node_id(cls, node_id: str) -> str:
        if not isinstance(node_id, str) or not node_id:
            msg = "update entry id must be a non-empty string"
            raise ValueError(msg)
        return node_id

    @field_validator("path", mode="before")
    @classmethod
    def validate_path_segments(cls, path: Any) -> Any:
        if not isinstance(path, (list, tuple)):
            return path
        for segment in path:
            # bool is a subclass of int; neither addresses anything. List items
            # are addressed by a selector, never by position.
            if isinstance(segment, (int, float)):
                msg = (
                    "update entry path segments must be object keys or selectors; integer list indexes are not allowed"
                )
                raise ValueError(msg)  # noqa: TRY004 - pydantic reports ValueError as a validation error
        return path

    @field_validator("path")
    @classmethod
    def validate_path(cls, path: NodeFieldPath) -> NodeFieldPath:
        if not path:
            msg = "update entry path must not be empty"
            raise ValueError(msg)
        return path


class SetNodeFieldUpdate(_NodeFieldUpdateBase):
    op: Literal["set_field"]
    value: Any


class DeleteNodeFieldUpdate(_NodeFieldUpdateBase):
    op: Literal["delete_field"]


UpdateNodeEntry = Annotated[
    SetNodeFieldUpdate | DeleteNodeFieldUpdate,
    Field(discriminator="op"),
]


class UpdateNodesOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_nodes"]
    updates: list[UpdateNodeEntry]


class UpdateEdgesOp(BaseModel):
    """Field writes to existing edges, addressed by edge id.

    A path may not start with ``id``, ``source`` or ``target``: connecting
    different nodes is a different edge, so it is a delete and an add.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["update_edges"]
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


FlowOperation = (
    AddNodesOp | UpdateNodesOp | DeleteNodesOp | AddEdgesOp | UpdateEdgesOp | DeleteEdgesOp | UpdateMetadataOp
)

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
        if operation_type == "update_edges":
            return UpdateEdgesOp.model_validate(operation)
        if operation_type == "delete_edges":
            return DeleteEdgesOp.model_validate(operation)
        if operation_type == "update_metadata":
            return UpdateMetadataOp.model_validate(operation)
    except ValidationError as exc:
        raise FlowOperationValidationError(str(exc)) from exc

    msg = f"Unsupported operation type: {operation_type!r}"
    raise FlowOperationValidationError(msg)


def deduplicate_delete_ids(ids: list[str]) -> list[str]:
    """Preserve first-seen order while removing duplicate delete IDs."""
    return list(dict.fromkeys(ids))


def dump_flow_operation(operation: FlowOperation) -> dict[str, Any]:
    """Serialize an operation to JSON-compatible data, omitting optional fields left unset.

    ``exclude_defaults`` rather than ``exclude_none``: a ``set_field`` whose
    value is ``null`` must keep that value.
    """
    return operation.model_dump(mode="json", exclude_defaults=True)
