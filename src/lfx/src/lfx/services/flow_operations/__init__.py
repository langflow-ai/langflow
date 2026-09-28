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
from lfx.services.flow_operations.canonical import (
    canonical_graph,
    canonical_graph_json,
    canonical_json,
    graph_hash,
    graphs_equal,
    json_type,
    values_equal,
)
from lfx.services.flow_operations.diff import DerivedFlowOperations, derive_flow_operations, diff_flow_data
from lfx.services.flow_operations.exceptions import (
    FlowDataValidationError,
    FlowOperationError,
    FlowOperationPreconditionError,
    FlowOperationReplayError,
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
from lfx.services.flow_operations.repair import REPAIRS, GraphFix, RepairResult, repair_flow_data
from lfx.services.flow_operations.schema import KeyedList, NodeSchema, load_node_schema
from lfx.services.flow_operations.service import BaseFlowOperationService
from lfx.services.flow_operations.validation import (
    GraphViolation,
    GraphViolationCode,
    find_graph_violations,
    validate_flow_data,
)

__all__ = [
    "REPAIRS",
    "AddEdgesOp",
    "AddNodesOp",
    "BaseFlowOperationService",
    "DeleteEdgesOp",
    "DeleteNodeFieldUpdate",
    "DeleteNodesOp",
    "DerivedFlowOperations",
    "ExpectAbsent",
    "ExpectValue",
    "Expectation",
    "FlowDataValidationError",
    "FlowOperation",
    "FlowOperationError",
    "FlowOperationPreconditionError",
    "FlowOperationReplayError",
    "FlowOperationValidationError",
    "FlowOperationsApplyResult",
    "GraphFix",
    "GraphState",
    "GraphViolation",
    "GraphViolationCode",
    "IdSelector",
    "KeySelector",
    "KeyedList",
    "NodeFieldPath",
    "NodeFieldPathSegment",
    "NodeSchema",
    "PythonFlowOperationService",
    "RepairResult",
    "SetNodeFieldUpdate",
    "UpdateEdgesOp",
    "UpdateMetadataOp",
    "UpdateNodeEntry",
    "UpdateNodesOp",
    "apply_flow_operations",
    "build_graph_state",
    "canonical_graph",
    "canonical_graph_json",
    "canonical_json",
    "deduplicate_delete_ids",
    "derive_flow_operations",
    "diff_flow_data",
    "dump_flow_operation",
    "finalize_graph",
    "find_graph_violations",
    "graph_hash",
    "graphs_equal",
    "json_type",
    "load_node_schema",
    "normalize_requested_ops",
    "parse_flow_operation",
    "parse_flow_operations",
    "repair_flow_data",
    "validate_flow_data",
    "values_equal",
]
