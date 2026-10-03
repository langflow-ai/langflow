"""Flow operation vocabulary and pure apply engine.

Operations describe granular edits to ``flow.data``: nodes and edges added,
updated field by field, or deleted, and top-level metadata changes. Paths
address object keys, and items of the lists ``node_schema.json`` declares
keyed by selector, never by index. The engine
has no transport or database dependencies, so the same rules apply wherever an
operation comes from.
"""

from lfx.services.flow_operations.apply import (
    FlowOperationsApplyResult,
    GraphState,
    apply_flow_operations,
    build_graph_state,
    finalize_graph,
)
from lfx.services.flow_operations.canonical import values_equal
from lfx.services.flow_operations.exceptions import (
    FlowDataValidationError,
    FlowOperationError,
    FlowOperationPreconditionError,
    FlowOperationValidationError,
)
from lfx.services.flow_operations.ops import (
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodeFieldUpdate,
    DeleteNodesOp,
    ExpectAbsent,
    Expectation,
    ExpectValue,
    FlowOperation,
    IdSelector,
    KeySelector,
    NodeFieldPath,
    NodeFieldPathSegment,
    SetNodeFieldUpdate,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodeEntry,
    UpdateNodesOp,
    deduplicate_delete_ids,
    dump_flow_operation,
    normalize_requested_ops,
    parse_flow_operation,
    parse_flow_operations,
)
from lfx.services.flow_operations.python import PythonFlowOperationService
from lfx.services.flow_operations.schema import KeyedList, NodeSchema, load_node_schema
from lfx.services.flow_operations.service import BaseFlowOperationService

__all__ = [
    "AddEdgesOp",
    "AddNodesOp",
    "BaseFlowOperationService",
    "DeleteEdgesOp",
    "DeleteNodeFieldUpdate",
    "DeleteNodesOp",
    "ExpectAbsent",
    "ExpectValue",
    "Expectation",
    "FlowDataValidationError",
    "FlowOperation",
    "FlowOperationError",
    "FlowOperationPreconditionError",
    "FlowOperationValidationError",
    "FlowOperationsApplyResult",
    "GraphState",
    "IdSelector",
    "KeySelector",
    "KeyedList",
    "NodeFieldPath",
    "NodeFieldPathSegment",
    "NodeSchema",
    "PythonFlowOperationService",
    "SetNodeFieldUpdate",
    "UpdateEdgesOp",
    "UpdateMetadataOp",
    "UpdateNodeEntry",
    "UpdateNodesOp",
    "apply_flow_operations",
    "build_graph_state",
    "deduplicate_delete_ids",
    "dump_flow_operation",
    "finalize_graph",
    "load_node_schema",
    "normalize_requested_ops",
    "parse_flow_operation",
    "parse_flow_operations",
    "values_equal",
]
