# ruff: noqa: INP001
"""Generate the shared fixtures whose expected outputs come from the Python engine.

The expected outputs of these files come from the Python engine
(``lfx.services.flow_operations`` and the pure parts of
``langflow.services.flow_history``), never from the Rust engine. Run this
against the Python engine at the reference commit (``ad19da0df4``,
``oplog-history-ui``), with ``lfx`` and ``langflow`` importable:

    python src/lfx-native/fixtures/tools/generate.py

It rewrites ``canonical_cases.json``, ``validation_cases.json``,
``repair_cases.json``, ``table_cases.json``, ``envelope_cases.json``,
``replay_cases.json``, ``restore_cases.json`` and ``write_cases.json`` next to
the other fixtures.

Two conventions keep the files runnable in every runtime:

- A graph whose number text matters (a number JavaScript reads as Infinity,
  or ``1.0`` against ``1``) is stored as JSON text in a ``*_json`` field, so a
  runner hands the engine the exact text.
- An id the engine draws at random is stored as ``<generated edge id>`` or
  ``<generated row id>``. A runner accepts any id of that shape there.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import lfx.services.flow_operations.repair as repair_module
import lfx.services.flow_operations.table_rows as table_rows_module
from langflow.services.flow_history import envelope as envelope_module
from langflow.services.flow_history.errors import FlowHistoryCorruptionError, RestoreFixNotAllowedError
from langflow.services.flow_history.restore_fixes import apply_restore_fixes
from lfx.services.flow_operations import (
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodesOp,
    FlowDataValidationError,
    FlowOperationError,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodesOp,
    canonical_json,
    derive_flow_operations,
    dump_flow_operation,
    find_graph_violations,
    graph_hash,
    graphs_equal,
    ordered_rows,
    parse_flow_operation,
    parse_flow_operations,
    parse_handle,
    repair_flow_data,
)
from lfx.services.flow_operations.edge_rules import escape_handle
from lfx.services.flow_operations.table_rows import (
    assign_changed_table_row_ids,
    assign_row_ids,
    assign_table_row_ids,
    fill_missing_positions,
    strip_flow_table_row_keys,
    strip_row_keys,
)

sys.path.insert(0, str(Path(__file__).parent))
from fixture_json import dumps

FIXTURES = Path(__file__).resolve().parent.parent
REFERENCE = "the Python engine at ad19da0df4 (oplog-history-ui)"
GENERATED_EDGE_ID = "<generated edge id>"
GENERATED_ROW_ID = "<generated row id>"
ACTOR = "11111111-1111-4111-8111-111111111111"
OTHER_ACTOR = "22222222-2222-4222-8222-222222222222"
REQUEST = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_REQUEST = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
EMPTY = {"nodes": [], "edges": []}

# --- Generated ids ------------------------------------------------------------------------

_counter = {"edge": 0, "row": 0}


def _edge_id() -> str:
    _counter["edge"] += 1
    return f"{GENERATED_EDGE_ID}#{_counter['edge']}"


def _row_id() -> str:
    _counter["row"] += 1
    return f"{GENERATED_ROW_ID}#{_counter['row']}"


repair_module.new_edge_id = _edge_id
table_rows_module.new_table_row_id = _row_id


def _placeholders(value: Any) -> Any:
    """Replace each generated id with its placeholder."""
    if isinstance(value, str):
        for placeholder in (GENERATED_EDGE_ID, GENERATED_ROW_ID):
            if value.startswith(placeholder + "#"):
                return placeholder
        return value
    if isinstance(value, list):
        return [_placeholders(item) for item in value]
    if isinstance(value, dict):
        return {key: _placeholders(item) for key, item in value.items()}
    return value


def _fresh(value: Any) -> Any:
    """A copy of a JSON value through JSON text, so no two places in it share an object."""
    return json.loads(json.dumps(value))


def _error(exc: Exception) -> dict[str, Any]:
    return {"error": type(exc).__name__, "code": exc.code}


def _write(name: str, document: dict[str, Any]) -> None:
    (FIXTURES / name).write_text(dumps(document), encoding="utf-8")


# --- Shared graph pieces ------------------------------------------------------------------


def _node(node_id: str, template: dict | None = None, outputs: list | None = None, **extra: Any) -> dict:
    body: dict[str, Any] = {"template": template if template is not None else {}}
    if outputs is not None:
        body["outputs"] = outputs
    return {"id": node_id, "data": {"node": body}, **extra}


def _edge(edge_id: str, source: str, target: str, source_handle: dict, target_handle: dict) -> dict:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "sourceHandle": escape_handle(source_handle),
        "targetHandle": escape_handle(target_handle),
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
    }


def _connectable(*edges: dict) -> dict:
    return {
        "nodes": [
            _node("a", outputs=[{"name": "out"}, {"name": "loop", "allows_loop": True}]),
            _node("b", {"f": {"type": "str"}, "many": {"type": "str", "list": True}}, outputs=[]),
            {"id": "note", "type": "noteNode", "data": {"node": {"template": {}}}},
        ],
        "edges": list(edges),
    }


def _edge_to(field: str, edge_id: str = "e", source_handle: dict | None = None) -> dict:
    return _edge(edge_id, "a", "b", source_handle or {"name": "out"}, {"fieldName": field})


def _legacy_edge(edge_id: str = "old") -> dict:
    """An edge older editors wrote: handle strings that are not JSON, and no data."""
    return {"id": edge_id, "source": "a", "target": "b", "sourceHandle": "x|y", "targetHandle": "z"}


def _table_graph(rows: Any, node_id: str = "api") -> dict:
    return {
        "nodes": [
            _node(
                node_id,
                {
                    "headers": {"type": "table", "_input_type": "TableInput", "value": rows},
                    "url": {"type": "str", "value": "http://x"},
                },
            )
        ],
        "edges": [],
    }


LEGACY_ROWS = [{"key": "Accept", "value": "json"}, {"key": "Auth", "value": "token"}]
KEYED_ROWS = [
    {"_id": "r1", "_pos": 1, "key": "Accept", "value": "json"},
    {"_id": "r2", "_pos": 2, "key": "Auth", "value": "token"},
]

# --- canonical_cases.json -----------------------------------------------------------------

NUMBERS = [
    ("zero", "0"),
    ("negative zero integer", "-0"),
    ("negative zero float", "-0.0"),
    ("an integral float", "1.0"),
    ("a negative fraction", "-1.5"),
    ("one tenth", "0.1"),
    ("a fraction", "123.456"),
    ("an exponent that prints plainly", "1e20"),
    ("the first exponent that prints with e", "1e21"),
    ("a mantissa with an exponent", "1.5e21"),
    ("the smallest plain fraction", "0.000001"),
    ("the largest small exponent", "1e-7"),
    ("a small mantissa", "1.25e-7"),
    ("the smallest double", "5e-324"),
    ("the largest double", "1.7976931348623157e308"),
    ("many digits", "333333333.3333333"),
    ("2^53", "9007199254740992"),
    ("2^53 + 1 rounds as a double", "9007199254740993"),
    ("a negative integer beyond 2^53", "-9007199254740993"),
    ("a large integer", "12345678901234567890123"),
    ("an upper-case exponent", "1E2"),
    ("a float spelled with an exponent", "2.5e-3"),
    ("the largest integer below the double overflow", str(2**1024 - 2**970 - 1)),
]
NON_FINITE = [
    ("an exponent beyond the double range", "1e400"),
    ("a negative exponent beyond the double range", "-1e400"),
    ("the integer at the double overflow", str(2**1024 - 2**970)),
    ("an integer beyond the double range", "1" + "0" * 309),
]
VALUES = [
    (
        "keys sort by UTF-16 code units",
        json.dumps({"€": 1, "\r": 2, "דּ": 3, "1": 4, "\U0001f600": 5, "\u0080": 6, "ö": 7}),
    ),
    ("strings escape only what JSON requires", json.dumps('a"b\\c\n\u0001\u001fé/\u007f\u2028')),
    ("literals and containers", '{"b": [true, false, null], "a": {}}'),
    ("nested objects sort at every level", '{"z": {"b": 1, "a": [{"d": 1, "c": 2}]}, "y": []}'),
]
EQUALITY_SAMPLES = [
    "null",
    "true",
    "false",
    "0",
    "0.0",
    "-0.0",
    "1",
    "1.0",
    "1.5",
    "9007199254740992",
    "9007199254740993",
    "9007199254740992.0",
    "1e21",
    '""',
    '"a"',
    '"1"',
    "[]",
    "[1]",
    "[1.0]",
    "[1, 2]",
    "[2, 1]",
    "{}",
    '{"a": 1}',
    '{"a": 1.0}',
    '{"b": 1}',
    '{"a": 1, "b": [true, null]}',
    '{"b": [true, null], "a": 1}',
    '{"a": {"b": {"c": 0}}}',
    '{"a": {"b": {"c": -0.0}}}',
    '{"a": {"b": {"c": 1}}}',
]
HANDLES = [
    ("a compact handle", "{œnameœ:œoutœ}"),
    ("a spaced handle", "{œnameœ: œoutœ, œtypesœ: [œMessageœ]}"),
    ("an escaped quote inside a handle", "{œnameœ:œa\\œbœ}"),
    ("NaN does not parse", "{œxœ:NaN}"),
    ("Infinity does not parse", "{œxœ:Infinity}"),
    ("a list is not a handle", "[1]"),
    ("plain text is not a handle", "x|y"),
    ("an empty string is not a handle", ""),
]


def _graph_pairs() -> list[tuple[str, dict, dict]]:
    base = _connectable(_edge_to("f"))
    reordered = _fresh(base)
    reordered["nodes"].reverse()
    view = _fresh(base)
    view["viewport"] = {"x": 1, "y": 2, "zoom": 1.5}
    view["nodes"][0].update({"selected": True, "dragging": False, "measured": {"width": 1}, "width": 3, "height": 4})
    view["nodes"][0]["data"]["node"]["last_updated"] = "2026-10-15"
    view["nodes"][1]["data"]["node"]["template"]["f"]["display_name"] = "F"
    view["edges"][0].update({"selected": True, "animated": True, "className": "running"})
    respelled = _fresh(base)
    respelled["edges"][0]["sourceHandle"] = "{œnameœ: œoutœ}"
    moved = _fresh(base)
    moved["nodes"][0]["position"] = {"x": 1, "y": 2}
    integral = _fresh(base)
    integral["nodes"][1]["data"]["node"]["template"]["f"]["value"] = 1
    as_float = _fresh(integral)
    as_float["nodes"][1]["data"]["node"]["template"]["f"]["value"] = 1.0
    as_bool = _fresh(integral)
    as_bool["nodes"][1]["data"]["node"]["template"]["f"]["value"] = True
    table = _table_graph(KEYED_ROWS)
    table_reordered = _table_graph(list(reversed(KEYED_ROWS)))
    legacy = _table_graph(LEGACY_ROWS)
    legacy_reordered = _table_graph(list(reversed(LEGACY_ROWS)))
    duplicate_ids = {"nodes": [_node("a"), _node("a")], "edges": []}
    return [
        ("node and edge order is not state", base, reordered),
        ("view state is not state", base, view),
        ("two spellings of one handle are one handle", base, respelled),
        ("a position is state", base, moved),
        ("1 and 1.0 are one number", integral, as_float),
        ("true and 1 differ", integral, as_bool),
        ("table row order is not state", table, table_reordered),
        ("a legacy table's array order is its order", legacy, legacy_reordered),
        ("graphs whose node ids repeat compare as lists", duplicate_ids, _fresh(duplicate_ids)),
    ]


def canonical_cases() -> dict[str, Any]:
    numbers = [{"name": name, "json": text, "canonical": canonical_json(json.loads(text))} for name, text in NUMBERS]
    for name, text in NON_FINITE:
        try:
            canonical_json(json.loads(text))
        except FlowDataValidationError as exc:
            numbers.append({"name": name, "json": text, "error": _error(exc)})
        else:
            raise AssertionError(name)
    graphs = []
    for name, left, right in _graph_pairs():
        graphs.append(
            {
                "name": name,
                "left": left,
                "right": right,
                "equal": graphs_equal(left, right),
                "left_hash": graph_hash(left),
                "right_hash": graph_hash(right),
            }
        )
    return {
        "description": (
            "Canonical form (RFC 8785), value equality and graph equality. Expected outputs come from "
            f"{REFERENCE}. `numbers` and `values` give JSON text and its canonical text, or the error. "
            "Any two `equality_samples` are equal exactly when their canonical texts are equal. `graphs` "
            "give two graphs, whether they are equal, and each one's graph_hash. `handles` give a handle "
            "value and the object it parses to, or null."
        ),
        "numbers": numbers,
        "values": [
            {"name": name, "json": text, "canonical": canonical_json(json.loads(text))} for name, text in VALUES
        ],
        "equality_samples": [
            {"json": text, "canonical": canonical_json(json.loads(text))} for text in EQUALITY_SAMPLES
        ],
        "graphs": graphs,
        "handles": [{"name": name, "handle": handle, "parsed": parse_handle(handle)} for name, handle in HANDLES],
    }


# --- validation_cases.json ----------------------------------------------------------------


def _validation_inputs() -> list[dict[str, Any]]:
    def graph() -> dict:
        return {"nodes": [_node("a"), _node("b")], "edges": [{"id": "e", "source": "a", "target": "b"}]}

    duplicates = graph()
    duplicates["nodes"] += [_node("a"), {"id": "", "data": {"node": {"template": {}}}}]
    edge_ids = graph()
    edge_ids["edges"] += [{"id": "e", "source": "a", "target": "b"}, {"source": "a", "target": "b"}]
    endpoints = graph()
    endpoints["edges"] = [{"id": "e1", "target": "b"}, {"id": "e2", "source": "a", "target": "zz"}]
    cases: list[dict[str, Any]] = [
        {"name": "a valid graph has no violations", "flow": graph()},
        {"name": "flow data null is not an object", "flow": None},
        {"name": "flow data that is a list is not an object", "flow": []},
        {"name": "flow data that is a string is not an object", "flow": "flow"},
        {"name": "collections must be lists", "flow": {"nodes": None, "edges": {}}},
        {"name": "missing collections are not lists", "flow": {}},
        {"name": "entries must be objects", "flow": {"nodes": ["x"], "edges": [3]}},
        {"name": "node ids must be present and unique", "flow": duplicates},
        {"name": "edge ids must be present and unique", "flow": edge_ids},
        {"name": "edge endpoints must name existing nodes", "flow": endpoints},
    ]
    for data, label in [
        (None, "data null"),
        ({"node": []}, "data.node a list"),
        ({"node": {}}, "data.node.template missing"),
        ({"node": {"template": "x"}}, "data.node.template a string"),
    ]:
        broken = graph()
        broken["nodes"][0]["data"] = data
        cases.append({"name": f"node objects must be objects: {label}", "flow": broken})
    non_finite = json.dumps(graph()).replace(
        '"id": "a",', '"id": "a", "position": {"x": 1e400, "y": -1e400, "z": 1.5},'
    )
    big = json.dumps(graph()).replace('"id": "a",', f'"id": "a", "position": {{"x": 1{"0" * 309}, "y": {2**53 + 1}}},')
    cases += [
        {"name": "non-finite numbers are violations", "flow_json": non_finite},
        {
            "name": "non-finite numbers are not checked when values are skipped",
            "flow_json": non_finite,
            "check_values": False,
        },
        {"name": "an integer too large for a double is a non-finite number", "flow_json": big},
        {
            "name": "a non-finite number in metadata is a violation",
            "flow_json": '{"nodes": [], "edges": [], "zoom": 1e999, "list": [1, -1e999]}',
        },
        {
            "name": "every violation is reported, in document order",
            "flow": {
                "nodes": [_node("a"), _node("b"), _node("a")],
                "edges": [{"id": "e", "source": "a", "target": "b"}, {"id": "e2", "source": "a", "target": "zz"}],
            },
        },
    ]

    # Edge rules, against the stored graph a write replaces.
    cases += [
        {
            "name": "an added edge into a missing field is for the client",
            "flow": _connectable(_edge_to("missing")),
            "base": EMPTY,
        },
        {
            "name": "a second edge into a single input is refused",
            "flow": _connectable(_edge_to("f", "e1"), _edge_to("f", "e2")),
            "base": _connectable(_edge_to("f", "e1")),
        },
        {
            "name": "a list field takes many edges",
            "flow": _connectable(_edge_to("many", "e1"), _edge_to("many", "e2")),
            "base": EMPTY,
        },
        {
            "name": "a stored edge the write leaves alone is not checked",
            "flow": _connectable(_edge_to("missing")),
            "base": _connectable(_edge_to("missing")),
        },
        {
            "name": "rewiring a stored edge checks it",
            "flow": _connectable(_edge_to("missing")),
            "base": _connectable(_edge_to("f")),
        },
        {
            "name": "a broken edge found while checking another is reported once at itself",
            "flow": _connectable(_legacy_edge(), _edge_to("f", "good")),
            "base": EMPTY,
        },
        {
            "name": "a stored broken edge fails the check of an edge added into its node",
            "flow": _connectable(_legacy_edge(), _edge_to("f", "good")),
            "base": _connectable(_legacy_edge()),
        },
        {
            "name": "edge rules wait for a sound structure",
            "flow": {**_connectable(_edge_to("missing")), "nodes": [*_connectable()["nodes"], _node("a")]},
            "base": EMPTY,
        },
        {
            "name": "an edge with a note at one end",
            "flow": _connectable(_edge("n", "a", "note", {"name": "out"}, {"fieldName": "f"})),
            "base": EMPTY,
        },
        {
            "name": "a source handle naming a missing output",
            "flow": _connectable(_edge_to("f", source_handle={"name": "gone"})),
            "base": EMPTY,
        },
        {
            "name": "a loop edge into an output that allows loops",
            "flow": _connectable(_edge("l", "a", "a", {"name": "out"}, {"name": "loop"})),
            "base": EMPTY,
        },
        {
            "name": "a loop edge into an output that does not allow loops",
            "flow": _connectable(_edge("l", "a", "a", {"name": "loop"}, {"name": "out"})),
            "base": EMPTY,
        },
    ]
    one_form = _edge_to("f")
    del one_form["sourceHandle"]
    no_object = _edge_to("f")
    del no_object["data"]["targetHandle"]
    disagree = _edge_to("f")
    disagree["targetHandle"] = escape_handle({"fieldName": "many"})
    both_missing = _edge_to("f")
    del both_missing["sourceHandle"]
    del both_missing["data"]["sourceHandle"]
    null_data = _edge_to("f")
    null_data["data"] = None
    null_name = _edge("e", "a", "b", {"name": "out"}, {"fieldName": "f", "name": None})
    nan_handle = _edge_to("f")
    nan_handle["targetHandle"] = "{œfieldNameœ:œfœ,œxœ:NaN}"
    object_not_object = _edge_to("f")
    object_not_object["data"]["sourceHandle"] = "out"
    neither = _edge("e", "a", "b", {"name": "out"}, {"id": "b"})
    empty_output = _edge("e", "a", "b", {"name": ""}, {"fieldName": "f"})
    cases += [
        {"name": "a handle with one form missing", "flow": _connectable(one_form), "base": EMPTY},
        {"name": "a handle without its object form", "flow": _connectable(no_object), "base": EMPTY},
        {"name": "a handle whose forms disagree", "flow": _connectable(disagree), "base": EMPTY},
        {"name": "a handle missing in both forms", "flow": _connectable(both_missing), "base": EMPTY},
        {"name": "edge data that is null is invalid", "flow": _connectable(null_data), "base": EMPTY},
        {
            "name": "a target handle with fieldName and a null name names both",
            "flow": _connectable(null_name),
            "base": EMPTY,
        },
        {"name": "NaN in a handle string does not parse", "flow": _connectable(nan_handle), "base": EMPTY},
        {"name": "a handle object that is a string", "flow": _connectable(object_not_object), "base": EMPTY},
        {"name": "a target handle naming neither a field nor an output", "flow": _connectable(neither), "base": EMPTY},
        {"name": "a source handle with an empty name", "flow": _connectable(empty_output), "base": EMPTY},
    ]

    # Table rows, against the stored graph a write replaces.
    def rows_of(rows: list) -> dict:
        return _table_graph(rows)

    tools = _table_graph(KEYED_ROWS)
    tools["nodes"][0]["data"]["node"]["template"]["tools_metadata"] = {
        "type": "table",
        "value": [{"name": "tool", "tags": ["tool"]}, {"name": "other", "tags": ["other"]}],
    }
    other_field = _table_graph(KEYED_ROWS)
    other_field["nodes"][0]["data"]["node"]["template"]["list"] = {"type": "str", "value": [{"a": 1}]}
    input_type_only = _table_graph(LEGACY_ROWS)
    del input_type_only["nodes"][0]["data"]["node"]["template"]["headers"]["type"]
    type_only = _table_graph(LEGACY_ROWS)
    del type_only["nodes"][0]["data"]["node"]["template"]["headers"]["_input_type"]
    cases += [
        {"name": "tables are not checked without a base", "flow": rows_of(LEGACY_ROWS)},
        {"name": "an unchanged legacy table is accepted", "flow": rows_of(LEGACY_ROWS), "base": rows_of(LEGACY_ROWS)},
        {"name": "an added legacy table is refused", "flow": rows_of(LEGACY_ROWS), "base": EMPTY},
        {"name": "a keyed table is accepted when added", "flow": rows_of(KEYED_ROWS), "base": EMPTY},
        {
            "name": "a keyed table is accepted when changed",
            "flow": rows_of([{**KEYED_ROWS[0], "value": "xml"}, KEYED_ROWS[1]]),
            "base": rows_of(KEYED_ROWS),
        },
        {
            "name": "replacing a keyed table with rows without ids is refused",
            "flow": rows_of(LEGACY_ROWS),
            "base": rows_of(KEYED_ROWS),
        },
        {
            "name": "duplicate row ids are refused",
            "flow": rows_of([KEYED_ROWS[0], {**KEYED_ROWS[1], "_id": "r1"}]),
            "base": EMPTY,
        },
        {"name": "the stored order of rows is not checked", "flow": rows_of(list(reversed(KEYED_ROWS))), "base": EMPTY},
        {
            "name": "a position must be a number",
            "flow": rows_of(
                [{**KEYED_ROWS[0], "_pos": "1"}, {**KEYED_ROWS[1], "_pos": None}, {"_id": "r3", "_pos": True}]
            ),
            "base": EMPTY,
        },
        {
            "name": "a position must be finite",
            "flow_json": json.dumps(rows_of([KEYED_ROWS[0]])).replace('"_pos": 1', '"_pos": 1e400'),
            "base": EMPTY,
        },
        {"name": "a row must be an object", "flow": rows_of([KEYED_ROWS[0], "x", None]), "base": EMPTY},
        {
            "name": "a row id must be a non-empty string",
            "flow": rows_of([{**KEYED_ROWS[0], "_id": ""}, {**KEYED_ROWS[1], "_id": 2}]),
            "base": EMPTY,
        },
        {"name": "only table fields are checked", "flow": other_field, "base": EMPTY},
        {"name": "tool actions are a keyed list, not a table", "flow": tools, "base": EMPTY},
        {"name": "a field typed table is a table", "flow": type_only, "base": EMPTY},
        {"name": "a field whose input type is TableInput is a table", "flow": input_type_only, "base": EMPTY},
    ]
    return cases


def validation_cases() -> dict[str, Any]:
    cases = []
    for case in _validation_inputs():
        flow = json.loads(case["flow_json"]) if "flow_json" in case else case["flow"]
        try:
            violations = find_graph_violations(flow, check_values=case.get("check_values", True), base=case.get("base"))
        except FlowOperationError as exc:
            cases.append({**case, "error": _error(exc)})
        else:
            cases.append({**case, "violations": [violation.to_dict() for violation in violations]})
    return {
        "description": (
            "Graph rules: find_graph_violations(flow, check_values, base). Expected outputs come from "
            f"{REFERENCE}. A case gives `flow` (or `flow_json`, JSON text whose numbers matter), an optional "
            "`base` (the stored graph a write replaces) and `check_values` (default true), and the violations "
            "in order, each with its code, path, message, resolution and edge_id."
        ),
        "cases": cases,
    }


# --- repair_cases.json --------------------------------------------------------------------


def _prompt(node_id: Any, **extra: Any) -> dict:
    return {"id": node_id, "data": {"id": node_id, "type": "Prompt", "node": {"template": {}}}, **extra}


def _plain_edge(edge_id: str, source: str, target: str) -> dict:
    return {"id": edge_id, "source": source, "target": target, "sourceHandle": "S", "targetHandle": "T"}


def _repair_inputs() -> list[dict[str, Any]]:
    source_handle = {"id": "a", "name": "out"}
    target_handle = {"fieldName": "f", "id": "b"}

    def handled(edge_id: str, target: str = "b", handle: dict | None = None) -> dict:
        return _edge(edge_id, "a", target, source_handle, handle or target_handle)

    one_form = handled("e")
    del one_form["sourceHandle"]
    del one_form["data"]["targetHandle"]
    no_data = handled("e")
    del no_data["data"]
    left_alone = handled("e")
    del left_alone["sourceHandle"]
    null_data = handled("e")
    null_data["data"] = None
    no_id = _plain_edge("x", "a", "b")
    del no_id["id"]
    missing_id = _prompt("x")
    del missing_id["id"]
    missing_id["data"]["id"] = None
    return [
        {
            "name": "a valid graph is returned unchanged with no fixes",
            "flow": {
                "nodes": [_prompt("a"), _prompt("b")],
                "edges": [_plain_edge("e", "a", "b")],
                "viewport": {"zoom": 1},
            },
        },
        {"name": "flow data null becomes an empty flow", "flow": None},
        {"name": "flow data that is a list becomes an empty flow", "flow": []},
        {"name": "flow data that is a string becomes an empty flow", "flow": "x"},
        {
            "name": "non-list collections become empty lists",
            "flow": {"nodes": None, "edges": "x", "description": "kept"},
        },
        {"name": "missing collections become empty lists", "flow": {"description": "kept"}},
        {"name": "non-object entries are dropped", "flow": {"nodes": [_prompt("a"), 1], "edges": ["x"]}},
        {
            "name": "missing node objects become empty objects",
            "flow": {"nodes": [{"id": "a"}, {"id": "b", "data": {"node": {"template": None}}}], "edges": []},
        },
        {
            "name": "a missing node id gets a generated id in the editor shape",
            "flow": {"nodes": [missing_id], "edges": []},
        },
        {
            "name": "duplicate node ids keep the first node and its edges",
            "flow": {
                "nodes": [_prompt("a"), _prompt("a", position={"x": 1}), _prompt("b")],
                "edges": [_plain_edge("e", "a", "b")],
            },
        },
        {
            "name": "a node id that is not a string gets a generated id",
            "flow": {"nodes": [{"id": 3, "data": {"id": 3, "node": {"template": {}}}}], "edges": []},
        },
        {
            "name": "edges to unknown nodes are dropped",
            "flow": {"nodes": [_prompt("a")], "edges": [_plain_edge("e1", "a", "zz"), {"id": "e2", "target": "a"}]},
        },
        {
            "name": "missing and duplicate edge ids are opaque like the editor",
            "flow": {
                "nodes": [_prompt("a"), _prompt("b")],
                "edges": [_plain_edge("e", "a", "b"), _plain_edge("e", "b", "a"), no_id],
            },
        },
        {
            "name": "non-finite numbers become null",
            "flow_json": json.dumps(
                {"nodes": [_prompt("a", position={"x": "NAN", "y": 1})], "edges": [], "zoom": "INF"}
            )
            .replace('"NAN"', "1e400")
            .replace('"INF"', "-1e400"),
        },
        {
            "name": "an integer too large for a double becomes null",
            "flow_json": json.dumps(
                {"nodes": [_prompt("a", position={"x": "BIG", "y": 2**53 + 1})], "edges": []}
            ).replace('"BIG"', "1" + "0" * 309),
        },
        {
            "name": "non-finite numbers in nested containers are found containers last first",
            "flow_json": (
                '{"nodes": [], "edges": [], "a": [1e400, {"b": -1e400}], "c": {"d": [1e400], "e": 1e400}, "f": 1e400}'
            ),
        },
        {
            "name": "a badly broken graph comes out following every rule",
            "flow_json": json.dumps(
                {
                    "nodes": [
                        None,
                        {"id": 3},
                        {"id": "a", "data": []},
                        {"id": "a"},
                        {"data": {"node": {"template": 1}}},
                    ],
                    "edges": [{"id": "e"}, {"id": "e", "source": "a", "target": "a", "w": "NAN"}, 7],
                }
            ).replace('"NAN"', "1e400"),
        },
        {"name": "a handle missing one form gets it from the other", "flow": _connectable(one_form), "base": EMPTY},
        {
            "name": "an edge without data gets its handle objects from its strings",
            "flow": _connectable(no_data),
            "base": EMPTY,
        },
        {
            "name": "an edge that touches a note is dropped",
            "flow": _connectable(handled("e", target="note")),
            "base": EMPTY,
        },
        {
            "name": "a rule only the client can fix is refused",
            "flow": _connectable(
                handled("e", handle={"fieldName": "missing", "id": "b"}), handled("e-note", target="note")
            ),
            "base": EMPTY,
        },
        {"name": "edge data that is null is left to the client", "flow": _connectable(null_data), "base": EMPTY},
        {
            "name": "stored edges the write leaves alone are not repaired",
            "flow": _connectable(left_alone),
            "base": _connectable(left_alone),
        },
        {
            "name": "a legacy table gets ids and evenly spaced positions in row order",
            "flow": _table_graph(LEGACY_ROWS),
            "base": EMPTY,
        },
        {
            "name": "an unchanged legacy table is left alone",
            "flow": _table_graph(LEGACY_ROWS),
            "base": _table_graph(LEGACY_ROWS),
        },
        {"name": "a legacy table without a base is left alone", "flow": _table_graph(LEGACY_ROWS)},
        {
            "name": "a missing position is filled between its neighbours",
            "flow": _table_graph([KEYED_ROWS[0], {"_id": "r9", "key": "New"}, KEYED_ROWS[1]]),
            "base": EMPTY,
        },
        {
            "name": "duplicate row ids are regenerated and the stored order is kept",
            "flow": _table_graph([{**KEYED_ROWS[1]}, {**KEYED_ROWS[0], "_id": "r2"}, "not a row"]),
            "base": EMPTY,
        },
        {
            "name": "rows a table already held keep their ids",
            "flow": _table_graph(LEGACY_ROWS),
            "base": _table_graph(KEYED_ROWS),
        },
        {
            "name": "only a new row gets a new id",
            "flow": _table_graph([{"key": "Trace", "value": "on"}, *LEGACY_ROWS]),
            "base": _table_graph(KEYED_ROWS),
        },
        {
            "name": "rows before the first position count down from it",
            "flow": _table_graph([{"key": "x"}, {"key": "y"}, {"_id": "r1", "_pos": 5, "key": "z"}]),
            "base": EMPTY,
        },
        {
            "name": "rows after the last position count up from it",
            "flow": _table_graph([{"_id": "r1", "_pos": 2.5, "key": "z"}, {"key": "x"}, {"key": "y"}]),
            "base": EMPTY,
        },
        {
            "name": "rows between out-of-order neighbours follow the one before",
            "flow": _table_graph(
                [{"_id": "r1", "_pos": 3, "key": "a"}, {"key": "b"}, {"_id": "r2", "_pos": 1, "key": "c"}]
            ),
            "base": EMPTY,
        },
    ]


def repair_cases() -> dict[str, Any]:
    cases = []
    for case in _repair_inputs():
        flow = json.loads(case["flow_json"]) if "flow_json" in case else case["flow"]
        try:
            result = repair_flow_data(_fresh(flow), base=case.get("base"))
        except FlowDataValidationError as exc:
            cases.append({**case, "error": {**_error(exc), "violations": [v.to_dict() for v in exc.violations]}})
        else:
            cases.append(
                {
                    **case,
                    "expected": _placeholders(result.flow_data),
                    "fixes": [fix.to_dict() for fix in result.fixes],
                }
            )
    return {
        "description": (
            "Repair: repair_flow_data(flow, base). Expected outputs come from "
            f"{REFERENCE}. A case gives `flow` (or `flow_json`) and an optional `base`, and either the "
            "repaired graph with the fixes in the order repair made them, or the error with the violations "
            "only the client can fix. Generated node ids are derived from content, so they are exact; edge "
            f"and row ids are random, so they appear as `{GENERATED_EDGE_ID}` and `{GENERATED_ROW_ID}`."
        ),
        "cases": cases,
    }


# --- table_cases.json ---------------------------------------------------------------------


def table_cases() -> dict[str, Any]:
    strip_inputs = [
        ("rows are stripped and put in order", list(reversed(KEYED_ROWS))),
        ("ties in position are ordered by id", [{"_id": "b", "_pos": 1, "k": 1}, {"_id": "a", "_pos": 1, "k": 2}]),
        ("ids order by UTF-16 code units", [{"_id": "דּ", "_pos": 1}, {"_id": "\U0001f600", "_pos": 1}]),
        ("1 and 1.0 are one position", [{"_id": "b", "_pos": 1.0}, {"_id": "a", "_pos": 1}]),
        ("a legacy table keeps its order", LEGACY_ROWS),
        ("a table with one row without a position keeps its order", [{"_id": "b", "_pos": 2}, {"_id": "a"}]),
        ("a value that is not a list is returned as is", None),
        ("rows that are not objects are kept", ["x", 1]),
    ]
    fill_inputs = [
        ("no positions at all become 1..n", [{"k": 1}, {"k": 2}, {"k": 3}]),
        ("a run between two positions is spread evenly", [{"_pos": 1}, {"k": 1}, {"k": 2}, {"_pos": 2}]),
        ("a run after the last position counts up", [{"_pos": 1.5}, {"k": 1}, {"k": 2}]),
        ("a run before the first position counts down", [{"k": 1}, {"k": 2}, {"_pos": 10}]),
        ("a run between out-of-order neighbours follows the one before", [{"_pos": 3}, {"k": 1}, {"_pos": 1}]),
        ("non-numeric positions are replaced", [{"_pos": "a0"}, {"_pos": True}, {"_pos": None}]),
        ("a gap with no room left is filled without renumbering", [{"_pos": 1}, {"k": 1}, {"_pos": 1 + 2**-52}]),
        ("valid positions are kept", [{"_pos": 7}, {"_pos": -2.5}]),
    ]
    assign_inputs = [
        ("new rows get random ids and positions in order", LEGACY_ROWS, None),
        (
            "existing ids and positions are kept and gaps filled",
            [
                {"_id": "r1", "_pos": 1, "key": "first"},
                {"key": "second"},
                {"_id": "r1", "_pos": 2, "key": "duplicate id"},
            ],
            None,
        ),
        ("a row equal to a stored row takes its id and position", LEGACY_ROWS, KEYED_ROWS),
        ("a stored row matches at most one row", [LEGACY_ROWS[0], LEGACY_ROWS[0]], KEYED_ROWS),
        ("a row with a position keeps it when matched", [{**LEGACY_ROWS[1], "_pos": 9}], KEYED_ROWS),
        ("a table with a row that is not an object is left alone", [LEGACY_ROWS[0], "x"], None),
    ]
    tools = _table_graph(_fresh(KEYED_ROWS))
    tools["nodes"][0]["data"]["node"]["template"]["tools_metadata"] = {
        "type": "table",
        "value": [{"name": "tool", "tags": ["tool"]}],
    }
    changed_inputs = [
        (
            "a changed table keeps the ids of rows it still holds",
            _table_graph(KEYED_ROWS),
            _table_graph([*LEGACY_ROWS, {"key": "New", "value": "x"}]),
        ),
        (
            "an unchanged legacy table is left alone",
            _table_graph(LEGACY_ROWS),
            {
                **_table_graph(LEGACY_ROWS),
                "nodes": [
                    _node(
                        "api",
                        {
                            "headers": {"type": "table", "_input_type": "TableInput", "value": LEGACY_ROWS},
                            "url": {"type": "str", "value": "http://y"},
                        },
                    )
                ],
            },
        ),
        ("a new node's tables get ids", EMPTY, _table_graph(LEGACY_ROWS)),
        ("valid tables and other fields are left alone", EMPTY, tools),
    ]
    strip_flow = _table_graph(_fresh(list(reversed(KEYED_ROWS))))
    group = _node("group")
    group["data"]["node"]["flow"] = {"data": _table_graph(_fresh(KEYED_ROWS))}
    strip_flow["nodes"].append(group)
    assign_node = _table_graph(_fresh(LEGACY_ROWS))
    assign_node["nodes"][0]["data"]["node"]["template"]["tools_metadata"] = {
        "type": "table",
        "value": [{"name": "tool", "tags": ["tool"]}],
    }

    def run_fill(rows: list) -> dict[str, Any]:
        rows = _fresh(rows)
        filled = fill_missing_positions(rows)
        return {"expected": rows, "filled": filled}

    def run_assign(rows: list, previous: list | None) -> list:
        rows = _fresh(rows)
        return _placeholders(assign_row_ids(rows, _fresh(previous)))

    def run_changed(base: dict, target: dict) -> dict:
        target = _fresh(target)
        return _placeholders(assign_changed_table_row_ids(_fresh(base), target))

    node = _fresh(assign_node["nodes"][0])
    assign_table_row_ids(node)
    return {
        "description": (
            "Table rows: the helpers that order, strip and assign row ids and positions. Expected outputs "
            f"come from {REFERENCE}. `strip` is strip_row_keys(rows); `fill_positions` is "
            "fill_missing_positions(rows), which never renumbers, with the indexes it filled; `assign` is "
            "assign_row_ids(rows, previous); `assign_node` is assign_table_row_ids(node); `assign_changed` "
            "is assign_changed_table_row_ids(base, target), the resulting target; `strip_flow` is "
            f"strip_flow_table_row_keys(flow). Random row ids appear as `{GENERATED_ROW_ID}`. Positions are "
            "compared as numbers, so 2 and 2.0 are one position."
        ),
        "strip": [
            {"name": name, "rows": rows, "expected": strip_row_keys(_fresh(rows))} for name, rows in strip_inputs
        ],
        "ordered": [
            {"name": name, "rows": rows, "expected": ordered_rows(rows)}
            for name, rows in strip_inputs
            if isinstance(rows, list)
        ],
        "fill_positions": [{"name": name, "rows": rows, **run_fill(rows)} for name, rows in fill_inputs],
        "assign": [
            {"name": name, "rows": rows, "previous": previous, "expected": run_assign(rows, previous)}
            for name, rows, previous in assign_inputs
        ],
        "assign_node": [
            {
                "name": "every table of a new node gets ids; tool actions are not a table",
                "node": assign_node["nodes"][0],
                "expected": _placeholders(node),
            }
        ],
        "assign_changed": [
            {"name": name, "base": base, "target": target, "expected": run_changed(base, target)}
            for name, base, target in changed_inputs
        ],
        "strip_flow": [
            {
                "name": "every top-level table is stripped and ordered; a group's flow is not touched",
                "flow": strip_flow,
                "expected": strip_flow_table_row_keys(_fresh(strip_flow)),
            }
        ],
    }


# --- envelope_cases.json ------------------------------------------------------------------


def _row(start: int, end: int, ops: Any) -> SimpleNamespace:
    return SimpleNamespace(flow_id=UUID(int=1), start_revision=start, end_revision=end, ops=ops)


def _element(revision: Any, operation: Any, cause: Any = None) -> dict:
    element = {"revision": revision, "operation": operation}
    if cause is not None:
        element["cause"] = cause
    return element


def _batch(request: str, actor: str, *elements: dict) -> dict:
    return {"request_id": request, "actor_user_id": actor, "operations": list(elements)}


DELETE_A = {"type": "delete_nodes", "ids": ["a"]}
DELETE_B = {"type": "delete_nodes", "ids": ["b"]}
META = {"type": "update_metadata", "fields": {"name": "x"}}


def _decode_inputs() -> list[tuple[str, int, int, Any]]:
    return [
        (
            "one batch",
            5,
            6,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(5, DELETE_A, "edit_code"), _element(6, META))]},
        ),
        (
            "two requests from two actors",
            1,
            3,
            {
                "version": 1,
                "batches": [
                    _batch(REQUEST, ACTOR, _element(1, DELETE_A)),
                    _batch(OTHER_REQUEST, OTHER_ACTOR, _element(2, DELETE_B), _element(3, META)),
                ],
            },
        ),
        (
            "ids in other spellings are normalized",
            1,
            1,
            {
                "version": 1,
                "batches": [
                    _batch(
                        "{AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA}",
                        "urn:uuid:11111111111141118111111111111111",
                        _element(1, DELETE_A),
                    )
                ],
            },
        ),
        (
            "a null cause is no cause",
            1,
            1,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, {"revision": 1, "cause": None, "operation": DELETE_A})]},
        ),
        (
            "a float revision equal to the expected one is accepted",
            1,
            1,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(1.0, DELETE_A))]},
        ),
        ("an unknown version", 1, 1, {"version": 2, "batches": [_batch(REQUEST, ACTOR, _element(1, DELETE_A))]}),
        ("an envelope that is not an object", 1, 1, [1]),
        ("batches that are not a list", 1, 1, {"version": 1, "batches": {}}),
        ("a batch without operations", 4, 4, {"version": 1, "batches": [_batch(REQUEST, ACTOR)]}),
        ("a batch that is not an object", 4, 4, {"version": 1, "batches": ["x"]}),
        (
            "a batch with a malformed request id",
            4,
            4,
            {"version": 1, "batches": [_batch("not-a-uuid", ACTOR, _element(4, DELETE_A))]},
        ),
        (
            "a batch without an actor",
            4,
            4,
            {"version": 1, "batches": [{"request_id": REQUEST, "operations": [_element(4, DELETE_A)]}]},
        ),
        (
            "a request with two batches",
            1,
            2,
            {
                "version": 1,
                "batches": [
                    _batch(REQUEST, ACTOR, _element(1, DELETE_A)),
                    _batch(REQUEST, ACTOR, _element(2, DELETE_B)),
                ],
            },
        ),
        (
            "a revision out of order",
            1,
            2,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(1, DELETE_A), _element(3, DELETE_B))]},
        ),
        ("an element that is not an object", 1, 1, {"version": 1, "batches": [_batch(REQUEST, ACTOR, "x")]}),
        (
            "a malformed operation",
            1,
            1,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(1, {"type": "rename"}))]},
        ),
        ("an element without an operation", 1, 1, {"version": 1, "batches": [_batch(REQUEST, ACTOR, {"revision": 1})]}),
        (
            "a cause that is not a string",
            1,
            1,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(1, DELETE_A, 5))]},
        ),
        (
            "fewer operations than the range",
            1,
            3,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(1, DELETE_A))]},
        ),
        (
            "more operations than the range",
            1,
            1,
            {"version": 1, "batches": [_batch(REQUEST, ACTOR, _element(1, DELETE_A), _element(2, DELETE_B))]},
        ),
    ]


def _decoded(operation: Any) -> dict:
    result = {
        "revision": operation.revision,
        "actor_user_id": str(operation.actor_user_id),
        "request_id": str(operation.request_id),
        "operation": dump_flow_operation(operation.operation),
    }
    if operation.cause is not None:
        result["cause"] = operation.cause
    return result


def _recorder_namespace(ops_limit: int, bytes_limit: int) -> dict[str, Any]:
    """The recorder's pure numbering and packing functions, read from its source and run as written."""
    spec = importlib.util.find_spec("langflow.services.flow_history.recorder")
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    wanted = {
        "normalize_absent_graph",
        "_json_size",
        "_sequence",
        "_pack_rows",
        "_split_to_fit",
        "_items",
        "_dump_item",
    }
    constants = {"_ENVELOPE_OVERHEAD", "_BATCH_OVERHEAD"}
    body = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in wanted)
        or (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets))
    ]
    settings = SimpleNamespace(flow_op_log_row_ops_limit=ops_limit, flow_op_log_row_bytes_limit=bytes_limit)
    namespace: dict[str, Any] = {
        "json": json,
        "UUID": UUID,
        "Any": Any,
        "AddEdgesOp": AddEdgesOp,
        "AddNodesOp": AddNodesOp,
        "DeleteEdgesOp": DeleteEdgesOp,
        "DeleteNodesOp": DeleteNodesOp,
        "UpdateEdgesOp": UpdateEdgesOp,
        "UpdateMetadataOp": UpdateMetadataOp,
        "UpdateNodesOp": UpdateNodesOp,
        "FlowOperation": object,
        "Flow": object,
        "RecordedOperation": envelope_module.RecordedOperation,
        "dump_flow_operation": dump_flow_operation,
        "encode_envelope": envelope_module.encode_envelope,
        "batch_header": envelope_module.batch_header,
        "get_settings_service": lambda: SimpleNamespace(settings=settings),
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), spec.origin, "exec"), namespace)  # noqa: S102
    return namespace


def _pack(case: dict[str, Any]) -> list[dict[str, Any]]:
    namespace = _recorder_namespace(case["limits"]["ops"], case["limits"]["bytes"])
    recorded = namespace["_sequence"](
        parse_flow_operations(_fresh(case["operations"])),
        flow=SimpleNamespace(latest_revision=case["latest_revision"]),
        actor_id=UUID(case["actor_user_id"]),
        request_id=UUID(case["request_id"]),
        cause=case.get("cause"),
    )
    return [
        {
            "start_revision": row[0].revision,
            "end_revision": row[-1].revision,
            "ops": envelope_module.encode_envelope(row),
            "actor_user_ids": envelope_module.distinct_actor_ids(row),
            "request_ids": envelope_module.request_ids_in_order(row),
        }
        for row in namespace["_pack_rows"](recorded)
    ]


def _pack_inputs() -> list[dict[str, Any]]:
    many_nodes = [_node(f"n{index}", {"text": {"type": "str", "value": "x" * 40}}) for index in range(6)]
    updates = [
        {"id": "a", "op": "set_field", "path": ["data", "node", "template", f"f{index}", "value"], "value": index}
        for index in range(5)
    ]
    return [
        {
            "name": "operations within both limits share one row",
            "operations": [DELETE_A, META],
            "latest_revision": 7,
            "limits": {"ops": 100, "bytes": 204800},
        },
        {
            "name": "the operation limit closes a row",
            "operations": [DELETE_A, DELETE_B, META],
            "latest_revision": 0,
            "limits": {"ops": 2, "bytes": 204800},
            "cause": "restore",
        },
        {
            "name": "the byte limit closes a row",
            "operations": [
                {"type": "add_nodes", "nodes": many_nodes[:2]},
                {"type": "add_nodes", "nodes": many_nodes[2:4]},
            ],
            "latest_revision": 3,
            "limits": {"ops": 100, "bytes": 600},
        },
        {
            "name": "a list that does not fit is split into operations of its type",
            "operations": [{"type": "add_nodes", "nodes": many_nodes}],
            "latest_revision": 0,
            "limits": {"ops": 100, "bytes": 700},
        },
        {
            "name": "an item larger than the limit is an operation of its own",
            "operations": [
                {
                    "type": "add_nodes",
                    "nodes": [_node("big", {"text": {"type": "str", "value": "x" * 900}}), many_nodes[0]],
                }
            ],
            "latest_revision": 0,
            "limits": {"ops": 100, "bytes": 500},
        },
        {
            "name": "updates split by the byte limit",
            "operations": [{"type": "update_nodes", "updates": updates}],
            "latest_revision": 10,
            "limits": {"ops": 100, "bytes": 450},
        },
        {
            "name": "deletes split by the byte limit",
            "operations": [{"type": "delete_edges", "ids": [f"edge-{index:03d}-{'x' * 30}" for index in range(12)]}],
            "latest_revision": 0,
            "limits": {"ops": 100, "bytes": 400},
        },
        {
            "name": "metadata splits into sets and deletes",
            "operations": [
                {
                    "type": "update_metadata",
                    "fields": {f"k{index}": "v" * 60 for index in range(4)},
                    "delete_keys": ["gone", "old"],
                }
            ],
            "latest_revision": 0,
            "limits": {"ops": 100, "bytes": 330},
        },
    ]


def envelope_cases() -> dict[str, Any]:
    decode = []
    for name, start, end, ops in _decode_inputs():
        row = {"start_revision": start, "end_revision": end, "ops": ops}
        try:
            decoded = envelope_module.decode_row(_row(start, end, _fresh(ops)))
        except FlowHistoryCorruptionError as exc:
            decode.append({"name": name, "row": row, "error": {"kind": exc.kind, "revision": exc.revision}})
        else:
            decode.append({"name": name, "row": row, "decoded": [_decoded(operation) for operation in decoded]})
    pack = []
    for inputs in _pack_inputs():
        case = {"actor_user_id": ACTOR, "request_id": REQUEST, **inputs}
        pack.append({**case, "rows": _pack(case)})
    two_requests = [
        envelope_module.RecordedOperation(1, UUID(ACTOR), UUID(REQUEST), parse_flow_operation(DELETE_A), "edit_code"),
        envelope_module.RecordedOperation(2, UUID(ACTOR), UUID(REQUEST), parse_flow_operation(META)),
        envelope_module.RecordedOperation(3, UUID(OTHER_ACTOR), UUID(OTHER_REQUEST), parse_flow_operation(DELETE_B)),
    ]
    encode = [
        {
            "name": "operations group into one batch per request",
            "operations": [_decoded(operation) for operation in two_requests],
            "envelope": envelope_module.encode_envelope(two_requests),
            "actor_user_ids": envelope_module.distinct_actor_ids(two_requests),
            "request_ids": envelope_module.request_ids_in_order(two_requests),
        }
    ]
    return {
        "description": (
            "The stored operation envelope. Expected outputs come from "
            f"{REFERENCE} (langflow.services.flow_history.envelope and the recorder's packing). `decode` "
            "gives a stored row and its operations, or the damage (`kind` and `revision`). `encode` gives "
            "recorded operations and their envelope, actors and requests. `pack` numbers operations from "
            "`latest_revision`, splits what does not fit, and packs them into rows within `limits` (sizes "
            "are compact JSON bytes)."
        ),
        "decode": decode,
        "encode": encode,
        "pack": pack,
    }


# --- replay_cases.json --------------------------------------------------------------------


def _replay_namespace(rows: list[SimpleNamespace]) -> dict[str, Any]:
    spec = importlib.util.find_spec("langflow.services.flow_history.replay")
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    body = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"replay_from", "verify_checkpoint"}
    ]

    async def rows_covering(_session: Any, _flow_id: Any, *, after: int, through: int) -> list:
        return [row for row in rows if row.end_revision > after and row.start_revision <= through]

    from lfx.services.flow_operations import apply_flow_operations

    namespace: dict[str, Any] = {
        "Any": Any,
        "UUID": UUID,
        "FlowVersion": object,
        "AsyncSession": object,
        "FlowOperationError": FlowOperationError,
        "FlowHistoryCorruptionError": FlowHistoryCorruptionError,
        "apply_flow_operations": apply_flow_operations,
        "graph_hash": graph_hash,
        "decode_row": envelope_module.decode_row,
        "rows_covering": rows_covering,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), spec.origin, "exec"), namespace)  # noqa: S102
    return namespace


def _replay_inputs() -> list[dict[str, Any]]:
    graph = {"nodes": [_node("a", {"x": {"type": "str", "value": "1"}}), _node("b")], "edges": [], "name": "flow"}

    def set_x(value: str) -> dict:
        return {
            "type": "update_nodes",
            "updates": [
                {"id": "a", "op": "set_field", "path": ["data", "node", "template", "x", "value"], "value": value}
            ],
        }

    rows = [
        {
            "start_revision": 1,
            "end_revision": 2,
            "ops": {
                "version": 1,
                "batches": [_batch(REQUEST, ACTOR, _element(1, set_x("2")), _element(2, set_x("3")))],
            },
        },
        {
            "start_revision": 3,
            "end_revision": 3,
            "ops": {"version": 1, "batches": [_batch(OTHER_REQUEST, OTHER_ACTOR, _element(3, DELETE_B))]},
        },
    ]
    gap = [
        rows[0],
        {
            **rows[1],
            "start_revision": 4,
            "end_revision": 4,
            "ops": {"version": 1, "batches": [_batch(OTHER_REQUEST, OTHER_ACTOR, _element(4, DELETE_B))]},
        },
    ]
    failing = [
        {
            "start_revision": 1,
            "end_revision": 1,
            "ops": {
                "version": 1,
                "batches": [_batch(REQUEST, ACTOR, _element(1, {"type": "delete_nodes", "ids": ["zz"]}))],
            },
        }
    ]
    damaged = [{"start_revision": 1, "end_revision": 1, "ops": {"version": 2, "batches": []}}]
    return [
        {"name": "replay to the end", "checkpoint": graph, "checkpoint_revision": 0, "rows": rows, "revision": 3},
        {
            "name": "replay stops inside a row",
            "checkpoint": graph,
            "checkpoint_revision": 0,
            "rows": rows,
            "revision": 1,
        },
        {
            "name": "a row that began before the checkpoint",
            "checkpoint": {**graph, "nodes": [_node("a", {"x": {"type": "str", "value": "2"}}), _node("b")]},
            "checkpoint_revision": 1,
            "rows": rows,
            "revision": 3,
        },
        {
            "name": "the checkpoint revision itself",
            "checkpoint": graph,
            "checkpoint_revision": 2,
            "rows": [],
            "revision": 2,
        },
        {"name": "a missing revision", "checkpoint": graph, "checkpoint_revision": 0, "rows": gap, "revision": 4},
        {
            "name": "rows that end before the revision",
            "checkpoint": graph,
            "checkpoint_revision": 0,
            "rows": rows[:1],
            "revision": 3,
        },
        {
            "name": "an operation that does not apply",
            "checkpoint": graph,
            "checkpoint_revision": 0,
            "rows": failing,
            "revision": 1,
        },
        {"name": "a damaged row", "checkpoint": graph, "checkpoint_revision": 0, "rows": damaged, "revision": 1},
    ]


def replay_cases() -> dict[str, Any]:
    cases = []
    for case in _replay_inputs():
        rows = [_row(row["start_revision"], row["end_revision"], _fresh(row["ops"])) for row in case["rows"]]
        namespace = _replay_namespace(rows)
        anchor = SimpleNamespace(
            flow_id=UUID(int=1), operation_revision=case["checkpoint_revision"], data=_fresh(case["checkpoint"])
        )
        try:
            graph = asyncio.run(namespace["replay_from"](None, UUID(int=1), anchor, case["revision"]))
        except FlowHistoryCorruptionError as exc:
            cases.append({**case, "error": {"kind": exc.kind, "revision": exc.revision}})
        else:
            cases.append({**case, "expected": graph})
    graph = _replay_inputs()[0]["checkpoint"]
    verify = []
    namespace = _replay_namespace([])
    for name, data, stored_hash in [
        ("a checkpoint that matches its hash", graph, graph_hash(graph)),
        ("a checkpoint changed after it was hashed", {**graph, "name": "changed"}, graph_hash(graph)),
    ]:
        checkpoint = SimpleNamespace(flow_id=UUID(int=1), operation_revision=4, data=data, graph_hash=stored_hash)
        try:
            namespace["verify_checkpoint"](checkpoint)
        except FlowHistoryCorruptionError as exc:
            verify.append(
                {
                    "name": name,
                    "graph": data,
                    "hash": stored_hash,
                    "revision": 4,
                    "error": {"kind": exc.kind, "revision": exc.revision},
                }
            )
        else:
            verify.append({"name": name, "graph": data, "hash": stored_hash, "revision": 4})
    return {
        "description": (
            "Replay onto a checkpoint. Expected outputs come from "
            f"{REFERENCE} (langflow.services.flow_history.replay). A case applies the operations of `rows` "
            "after `checkpoint_revision` up to `revision` to `checkpoint`, and gives the graph or the damage "
            "(`kind` and `revision`). `verify` checks a checkpoint's graph against its stored hash."
        ),
        "cases": cases,
        "verify": verify,
    }


# --- restore_cases.json -------------------------------------------------------------------


def _restore_inputs() -> list[dict[str, Any]]:
    stored = _connectable()
    broken = _connectable(_edge_to("missing", "bad"))
    occupied = _connectable(_edge_to("f", "e1"), _edge_to("f", "e2"))
    occupied_stored = _connectable(_edge_to("f", "e1"))
    no_data = _edge_to("missing", "bad")
    del no_data["data"]
    no_data_graph = _connectable(no_data)
    handles = {"sourceHandle": {"name": "out"}, "targetHandle": {"fieldName": "f"}}

    def rewrite(edge_id: str, path: list, value: Any) -> dict:
        return {"type": "update_edges", "updates": [{"id": edge_id, "op": "set_field", "path": path, "value": value}]}

    return [
        {
            "name": "deleting an edge whose handle names nothing",
            "revision": broken,
            "stored": stored,
            "fixes": [{"type": "delete_edges", "ids": ["bad"]}],
        },
        {
            "name": "rewriting the handles of an edge whose handle names nothing",
            "revision": broken,
            "stored": stored,
            "fixes": [
                rewrite("bad", ["targetHandle"], escape_handle({"fieldName": "f"})),
                rewrite("bad", ["data", "targetHandle"], {"fieldName": "f"}),
            ],
        },
        {
            "name": "setting data on an edge that has none",
            "revision": no_data_graph,
            "stored": stored,
            "fixes": [
                rewrite("bad", ["data"], handles),
                rewrite("bad", ["targetHandle"], escape_handle({"fieldName": "f"})),
            ],
        },
        {
            "name": "setting data with another key is an edit",
            "revision": no_data_graph,
            "stored": stored,
            "fixes": [rewrite("bad", ["data"], {**handles, "x": 1})],
        },
        {
            "name": "setting data on an edge that has it is an edit",
            "revision": broken,
            "stored": stored,
            "fixes": [rewrite("bad", ["data"], handles)],
        },
        {
            "name": "deleting either edge into an occupied input",
            "revision": occupied,
            "stored": occupied_stored,
            "fixes": [{"type": "delete_edges", "ids": ["e1"]}],
        },
        {
            "name": "deleting the edge that took an occupied input",
            "revision": occupied,
            "stored": occupied_stored,
            "fixes": [{"type": "delete_edges", "ids": ["e2"]}],
        },
        {
            "name": "rewriting an edge into an occupied input is not a fix",
            "revision": occupied,
            "stored": occupied_stored,
            "fixes": [rewrite("e2", ["targetHandle"], escape_handle({"fieldName": "many"}))],
        },
        {
            "name": "deleting an edge that breaks no rule is not a fix",
            "revision": _connectable(_edge_to("f", "good")),
            "stored": stored,
            "fixes": [{"type": "delete_edges", "ids": ["good"]}],
        },
        {
            "name": "a delete of a fixable edge with an unknown edge",
            "revision": broken,
            "stored": stored,
            "fixes": [{"type": "delete_edges", "ids": ["bad", "other"]}],
        },
        {
            "name": "a delete_field is not a handle rewrite",
            "revision": broken,
            "stored": stored,
            "fixes": [
                {"type": "update_edges", "updates": [{"id": "bad", "op": "delete_field", "path": ["targetHandle"]}]}
            ],
        },
        {
            "name": "a rewrite of another key is not a handle rewrite",
            "revision": broken,
            "stored": stored,
            "fixes": [rewrite("bad", ["label"], "x")],
        },
        {
            "name": "a fix the engine cannot apply keeps the engine's code",
            "revision": broken,
            "stored": stored,
            "fixes": [rewrite("bad", ["targetHandle"], 5)],
        },
        {"name": "no fixes", "revision": broken, "stored": stored, "fixes": []},
    ]


def restore_cases() -> dict[str, Any]:
    cases = []
    for case in _restore_inputs():
        fixes = parse_flow_operations(_fresh(case["fixes"]))
        try:
            graph = apply_restore_fixes(_fresh(case["revision"]), _fresh(case["stored"]), fixes)
        except RestoreFixNotAllowedError as exc:
            cases.append({**case, "error": _error(exc)})
        except FlowOperationError as exc:
            cases.append({**case, "error": _error(exc)})
        else:
            cases.append({**case, "expected": graph})
    return {
        "description": (
            "Restore fixes: apply_restore_fixes(revision, stored, fixes). Expected outputs come from "
            f"{REFERENCE} (langflow.services.flow_history.restore_fixes). A case gives the rebuilt revision, "
            "the stored flow it replaces and the client's fixes, and the fixed revision or the error."
        ),
        "cases": cases,
    }


# --- write_cases.json ---------------------------------------------------------------------


def _prepare_write(stored: Any, target: Any, options: dict[str, Any]) -> dict[str, Any]:
    """The recorder's write path without the database, composed from the Python engine as write_flow_graph runs it."""
    namespace = _recorder_namespace(options["limits"]["ops"], options["limits"]["bytes"])
    normalize = namespace["normalize_absent_graph"]
    repairs: list[dict[str, Any]] = []
    stored_repaired = False
    if options["started"]:
        base = stored
    else:
        base = normalize(stored)
        violations = find_graph_violations(base)
        if violations:
            if not options["repair_invalid_graph"]:
                return {"error": {"graph": "stored", "violations": [v.to_dict() for v in violations]}}
            repaired = repair_flow_data(base)
            base = repaired.flow_data
            stored_repaired = True
            repairs += [{"graph": "stored", **fix.to_dict()} for fix in repaired.fixes]
    target = normalize(target)
    violations = find_graph_violations(target, base=base)
    if violations:
        if not options["repair_invalid_graph"]:
            return {"error": {"graph": "submitted", "violations": [v.to_dict() for v in violations]}}
        try:
            repaired = repair_flow_data(target, base=base)
        except FlowDataValidationError as exc:
            return {"error": {"graph": "submitted", "violations": [v.to_dict() for v in exc.violations]}}
        target = repaired.flow_data
        repairs += [{"graph": "submitted", **fix.to_dict()} for fix in repaired.fixes]
    derived = derive_flow_operations(base, target)
    recorded = namespace["_sequence"](
        derived.operations,
        flow=SimpleNamespace(latest_revision=options["latest_revision"]),
        actor_id=UUID(options["actor_user_id"]),
        request_id=UUID(options["request_id"]),
        cause=options.get("cause"),
    )
    rows = [
        {
            "start_revision": row[0].revision,
            "end_revision": row[-1].revision,
            "ops": envelope_module.encode_envelope(row),
            "actor_user_ids": envelope_module.distinct_actor_ids(row),
            "request_ids": envelope_module.request_ids_in_order(row),
        }
        for row in namespace["_pack_rows"](recorded)
    ]
    return {
        "expected": _placeholders(
            {
                "base": base,
                "stored_repaired": stored_repaired,
                "target": target,
                "repairs": repairs,
                "operations": [dump_flow_operation(operation) for operation in derived.operations],
                "rows": rows,
            }
        )
    }


def write_cases() -> dict[str, Any]:
    options = {
        "started": True,
        "repair_invalid_graph": False,
        "latest_revision": 4,
        "actor_user_id": ACTOR,
        "request_id": REQUEST,
        "limits": {"ops": 100, "bytes": 204800},
    }
    graph = _connectable(_edge_to("f"))
    edited = _fresh(graph)
    edited["nodes"][1]["data"]["node"]["template"]["f"]["value"] = "hello"
    edited["name"] = "renamed"
    view_only = _fresh(graph)
    view_only["viewport"] = {"zoom": 2}
    broken_stored = {"nodes": [_node("a"), _node("a")], "edges": None}
    inputs = [
        ("an edit records its operations in rows", graph, edited, {**options, "cause": "edit_code"}),
        ("a save that changes only view state records nothing", graph, view_only, options),
        (
            "a flow without history and without data starts empty",
            None,
            graph,
            {**options, "started": False, "latest_revision": 0},
        ),
        (
            "a stored graph that breaks the rules is refused",
            broken_stored,
            graph,
            {**options, "started": False, "latest_revision": 0},
        ),
        (
            "a stored graph that breaks the rules is repaired on request",
            broken_stored,
            graph,
            {**options, "started": False, "latest_revision": 0, "repair_invalid_graph": True},
        ),
        ("a submitted legacy table is refused", EMPTY, _table_graph(LEGACY_ROWS), options),
        (
            "a submitted legacy table is repaired on request",
            EMPTY,
            _table_graph(LEGACY_ROWS),
            {**options, "repair_invalid_graph": True},
        ),
        (
            "a submitted edge only the client can fix is refused even with repair",
            _connectable(),
            _connectable(_edge_to("missing")),
            {**options, "repair_invalid_graph": True},
        ),
        (
            "operations past the row limit fill several rows",
            {"nodes": [_node("gone")], "edges": []},
            {"nodes": [_node(f"n{index}") for index in range(3)], "edges": [], "name": "x"},
            {**options, "limits": {"ops": 2, "bytes": 204800}},
        ),
    ]
    cases = []
    for name, stored, target, case_options in inputs:
        result = _prepare_write(_fresh(stored), _fresh(target), case_options)
        cases.append({"name": name, "stored": stored, "target": target, "options": case_options, **result})
    return {
        "description": (
            "The engine's part of a save: check, repair on request, derive, number and pack. Expected "
            f"outputs come from {REFERENCE}, composed from the recorder's write path (write_flow_graph) "
            "without its database steps. A case gives the stored graph, the submitted graph and the options, "
            "and either what the save stores or the graph whose violations refuse it. Random ids appear as "
            f"`{GENERATED_EDGE_ID}` and `{GENERATED_ROW_ID}`."
        ),
        "cases": cases,
    }


def main() -> None:
    for name, build in [
        ("canonical_cases.json", canonical_cases),
        ("validation_cases.json", validation_cases),
        ("repair_cases.json", repair_cases),
        ("table_cases.json", table_cases),
        ("envelope_cases.json", envelope_cases),
        ("replay_cases.json", replay_cases),
        ("restore_cases.json", restore_cases),
        ("write_cases.json", write_cases),
    ]:
        _write(name, build())
        print(f"wrote {name}")  # noqa: T201


if __name__ == "__main__":
    main()
