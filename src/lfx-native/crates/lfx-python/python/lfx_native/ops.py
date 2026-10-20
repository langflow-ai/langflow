"""The flow operation engine: apply, diff, validate, repair and hash flow graphs.

Every function takes JSON text and returns JSON text. An engine error is
raised as ``EngineError``: ``kind`` names the matching Python exception class
(``FlowOperationValidationError``, ``FlowDataValidationError``,
``FlowOperationReplayError``, ``RestoreFixNotAllowedError`` or
``FlowGraphInvalidError``), ``code`` is its stable code, and ``details`` is the
whole error as JSON text, with the violations, edge id or graph it carries.
"""

from lfx_native._native import (
    EngineError,
    GraphState,
    append_table_rows,
    apply,
    apply_restore_fixes,
    assign_changed_node_table_row_ids,
    assign_changed_table_row_ids,
    assign_row_ids,
    assign_table_row_ids,
    canonical_json,
    derive,
    diff,
    edge_fixes,
    fixes_for_edges,
    graph_hash,
    graphs_equal,
    new_edge_id,
    new_table_row_id,
    node_schema,
    normalize_operations,
    ordered_rows,
    prepare_write,
    repair,
    strip_flow_table_row_keys,
    strip_row_keys,
    table_fields,
    validate,
    values_equal,
)

__all__ = [
    "EngineError",
    "GraphState",
    "append_table_rows",
    "apply",
    "apply_restore_fixes",
    "assign_changed_node_table_row_ids",
    "assign_changed_table_row_ids",
    "assign_row_ids",
    "assign_table_row_ids",
    "canonical_json",
    "derive",
    "diff",
    "edge_fixes",
    "fixes_for_edges",
    "graph_hash",
    "graphs_equal",
    "new_edge_id",
    "new_table_row_id",
    "node_schema",
    "normalize_operations",
    "ordered_rows",
    "prepare_write",
    "repair",
    "strip_flow_table_row_keys",
    "strip_row_keys",
    "table_fields",
    "validate",
    "values_equal",
]
