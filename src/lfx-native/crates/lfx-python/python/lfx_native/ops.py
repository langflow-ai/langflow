"""The flow operation engine: apply, diff, validate, repair and hash flow graphs.

Every function takes Python values and returns Python values. An argument
that is ``bytes`` is UTF-8 JSON text; any other argument is the JSON value
itself (dict, list, tuple, str, int, float, bool or None), read with the same
limits as text: at most 127 levels deep, no lone surrogate, finite numbers.
A ``str`` is a JSON string, never text to parse.
Numbers come back as ``int`` or ``float``, as ``json.loads`` would read them.

An engine error is raised as ``EngineError``: ``kind`` names the matching
Python exception class (``FlowOperationValidationError``,
``FlowDataValidationError``, ``FlowOperationReplayError``,
``RestoreFixNotAllowedError`` or ``FlowGraphInvalidError``), ``code`` is its
stable code, and ``details`` is the whole error as a dict, with the
violations, edge id or graph it carries.
"""

from lfx_native._native import (
    EngineError,
    GraphPlain,
    GraphState,
    append_table_rows,
    apply,
    apply_restore_fixes,
    assign_changed_node_table_row_ids,
    assign_changed_table_row_ids,
    assign_row_ids,
    assign_table_row_ids,
    canonical_json,
    edge_fixes,
    fixes_for_edges,
    graph_hash,
    graphs_equal,
    new_edge_id,
    new_table_row_id,
    node_schema,
    ops_diff,
    ordered_rows,
    repair,
    strip_flow_table_row_keys,
    strip_row_keys,
    table_fields,
    validate,
    values_equal,
)

__all__ = [
    "EngineError",
    "GraphPlain",
    "GraphState",
    "append_table_rows",
    "apply",
    "apply_restore_fixes",
    "assign_changed_node_table_row_ids",
    "assign_changed_table_row_ids",
    "assign_row_ids",
    "assign_table_row_ids",
    "canonical_json",
    "edge_fixes",
    "fixes_for_edges",
    "graph_hash",
    "graphs_equal",
    "new_edge_id",
    "new_table_row_id",
    "node_schema",
    "ops_diff",
    "ordered_rows",
    "repair",
    "strip_flow_table_row_keys",
    "strip_row_keys",
    "table_fields",
    "validate",
    "values_equal",
]
