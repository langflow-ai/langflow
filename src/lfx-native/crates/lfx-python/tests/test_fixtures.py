"""Every shared fixture file, run through the Python binding.

The fixtures are the engine's specification; the Rust runner and the browser
binding's runner run the same files with the same checks. Every test runs
twice: with its arguments as JSON text (bytes), which keeps each number's
original text, and as Python objects. Results are Python objects, so they are compared
as Python sees them: numbers as `int` or `float`, as `json.loads` reads their
text. The Rust and Node runners compare the text of numbers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from lfx_native import ops

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
GENERATED_EDGE_ID = "<generated edge id>"
GENERATED_ROW_ID = "<generated row id>"


class Number(str):
    """A JSON number, kept as its text."""

    __slots__ = ()


def parse(text: str | bytes) -> Any:
    return json.loads(text, parse_float=Number, parse_int=Number)


def plain(value: Any) -> Any:
    """A value as Python holds JSON: each number as the int or float ``json.loads`` reads from its text."""
    if isinstance(value, Number):
        return json.loads(value)
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value


MODE = "text"


@pytest.fixture(autouse=True, params=["text", "objects"])
def argument_mode(request):
    """Run each test with JSON text arguments, then with Python object arguments."""
    global MODE  # noqa: PLW0603 -- read by arg() in every test
    MODE = request.param
    yield
    MODE = "text"


def arg(value: Any) -> Any:
    """A fixture value as an argument: JSON text (bytes) with each number as written, or Python objects."""
    return dump(value).encode() if MODE == "text" else plain(value)


def dump(value: Any) -> str:
    """JSON text of a value read by ``parse``, with every number as it was written."""
    if isinstance(value, Number):
        return str(value)
    if value is None or isinstance(value, (bool, str, int, float)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(dump(item) for item in value) + "]"
    return "{" + ",".join(f"{json.dumps(key, ensure_ascii=False)}:{dump(item)}" for key, item in value.items()) + "}"


def load(name: str) -> Any:
    return parse((FIXTURES / name).read_text(encoding="utf-8"))


def section(name: str, key: str) -> list[Any]:
    return [pytest.param(case, id=str(case.get("name", index))) for index, case in enumerate(load(name)[key])]


def strict(actual: Any, expected: Any) -> bool:
    """Equal as JSON: objects in any key order, numbers by their text."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(strict(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(strict(a, b) for a, b in zip(actual, expected, strict=True))
    return type(actual) is type(expected) and actual == expected


def matches(actual: Any, expected: Any) -> bool:
    """Equal as JSON, numbers by value, and a generated-id placeholder matching any id of its shape."""
    if expected == GENERATED_EDGE_ID and not isinstance(expected, Number):
        return isinstance(actual, str) and re.fullmatch(r"e-[0-9A-Za-z]{21}", actual) is not None
    if expected == GENERATED_ROW_ID and not isinstance(expected, Number):
        return isinstance(actual, str) and re.fullmatch(r"[0-9A-Za-z]{10}", actual) is not None
    if is_number(actual) and is_number(expected):
        return float(actual) == float(expected)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(matches(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(matches(a, b) for a, b in zip(actual, expected, strict=True))
    return type(actual) is type(expected) and actual == expected


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check(compare: Callable[[Any, Any], bool], what: str, actual: Any, expected: Any) -> None:
    actual, expected = plain(actual), plain(expected)
    assert compare(actual, expected), f"{what} differs\n  actual:   {dump(actual)}\n  expected: {dump(expected)}"


def failure(error: ops.EngineError) -> dict[str, Any]:
    return {"error": error.kind, "code": error.code}


def graph_arg(case: dict[str, Any], key: str) -> Any:
    """A case's graph as an argument: its exact ``<key>_json`` text when it has one."""
    return case[f"{key}_json"].encode() if f"{key}_json" in case else arg(case.get(key))


# --- apply_cases.json, merge_cases.json, property_cases.json ------------------------------


def ignoring_id_order(operations: list[Any]) -> list[Any]:
    return [
        {**operation, "ids": sorted(operation["ids"])}
        if operation["type"] in {"delete_nodes", "delete_edges"}
        else operation
        for operation in operations
    ]


def ignoring_order(flow: Any) -> Any:
    """Nodes, edges and table rows as collections keyed by id: their array order is not state."""
    flow = plain(flow)
    for key in ("nodes", "edges"):
        if key in flow:
            flow[key] = sorted(flow[key], key=lambda item: item["id"])
    for node in flow.get("nodes", []):
        for name in ops.table_fields(node):
            field = node["data"]["node"]["template"][name]
            field["value"] = sorted(field["value"], key=lambda row: row["__id__"])
    return flow


@pytest.mark.parametrize("case", section("apply_cases.json", "cases"))
def test_apply_case(case):
    try:
        state = ops.GraphState(arg(case["base"]))
    except ops.EngineError as error:
        check(strict, "error", failure(error), {"error": case.get("error"), "code": case.get("code")})
        return
    try:
        applied = state.apply(arg(case["operations"]), forward=True)
    except ops.EngineError as error:
        check(strict, "error", failure(error), {"error": case.get("error"), "code": case.get("code")})
        check(strict, "state after the refused batch", state.to_dict(), case["base"])
        return
    assert "error" not in case, "expected the operations to be refused"
    check(strict, "flow data", ignoring_order(state.to_dict()), ignoring_order(case["expected"]))
    check(strict, "flow data as text", parse(state.to_json()), state.to_dict())
    expected_forward = case.get("forward_operations", case["operations"])
    check(
        strict,
        "forward operations",
        ignoring_id_order(applied["forward_operations"]),
        ignoring_id_order(expected_forward),
    )


DOCUMENT = load("merge_cases.json")


@pytest.mark.parametrize("case", section("merge_cases.json", "cases"))
def test_merge_case(case):
    state = ops.GraphState(arg(DOCUMENT["base"]))
    outcomes = {}
    for name in case["order"]:
        before = state.to_dict()
        try:
            state.apply(arg(case["transactions"][name]))
        except ops.EngineError as error:
            check(strict, f"state after refusing {name}", state.to_dict(), before)
            outcomes[name] = failure(error)
        else:
            outcomes[name] = "applied"
    check(strict, "outcomes", outcomes, case["outcomes"])
    assert ops.graphs_equal(state.to_json().encode(), arg(case["expected"]))


PROPERTY = load("property_cases.json")


@pytest.mark.parametrize("sequence", section("property_cases.json", "sequences"))
def test_property_sequence(sequence):
    state = ops.GraphState(arg(PROPERTY["base"]))
    for transaction in sequence["transactions"]:
        state.apply(arg(transaction))
    assert ops.graph_hash(state.to_dict()) == ops.graph_hash(state.to_json().encode()) == sequence["graph_hash"]


# --- diff_cases.json --------------------------------------------------------------------------


@pytest.mark.parametrize("case", section("diff_cases.json", "cases"))
def test_diff_case(case):
    base, target = arg(case["base"]), arg(case["target"])
    check(strict, "operations", ops.diff(base, target), case["operations"])
    derived = ops.derive(base, target)
    assert list(derived) == ["operations"]
    replayed = ops.GraphState(base)
    replayed.apply(derived["operations"])
    assert ops.graphs_equal(replayed.to_dict(), target)
    state = ops.GraphState(base)
    for operation in case["operations"]:
        state.apply(arg([operation]))
    assert ops.graphs_equal(state.to_json().encode(), target)


# --- canonical_cases.json ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    section("canonical_cases.json", "numbers")
    + section("canonical_cases.json", "values")
    + section("limit_cases.json", "refused")
    + section("limit_cases.json", "accepted"),
)
def test_canonical_text(case):
    try:
        actual = {"canonical": ops.canonical_json(case["json"].encode())}
    except ops.EngineError as error:
        actual = {"error": failure(error)}
    expected = {"error": case["error"]} if "error" in case else {"canonical": case["canonical"]}
    check(strict, "canonical form", actual, expected)


def test_equality_samples():
    samples = load("canonical_cases.json")["equality_samples"]
    for left in samples:
        for right in samples:
            assert ops.values_equal(left["json"].encode(), right["json"].encode()) == (
                left["canonical"] == right["canonical"]
            )


@pytest.mark.parametrize("case", section("canonical_cases.json", "graphs"))
def test_graph_comparison(case):
    left, right = arg(case["left"]), arg(case["right"])
    assert ops.graphs_equal(left, right) == case["equal"]
    assert ops.graph_hash(left) == case["left_hash"]
    assert ops.graph_hash(right) == case["right_hash"]


# --- validation_cases.json, repair_cases.json -------------------------------------------------


@pytest.mark.parametrize("case", section("validation_cases.json", "cases"))
def test_validation_case(case):
    base = arg(case["base"]) if "base" in case else None
    try:
        actual = {
            "violations": ops.validate(graph_arg(case, "flow"), base, check_values=case.get("check_values", True))
        }
    except ops.EngineError as error:
        actual = {"error": failure(error)}
    expected = {"error": case["error"]} if "error" in case else {"violations": case["violations"]}
    check(strict, "violations", actual, expected)


@pytest.mark.parametrize("case", section("repair_cases.json", "cases"))
def test_repair_case(case):
    base = arg(case["base"]) if "base" in case else None
    try:
        repaired = ops.repair(graph_arg(case, "flow"), base)
        actual = {"expected": repaired["flow_data"], "fixes": repaired["fixes"]}
    except ops.EngineError as error:
        details = error.details
        actual = {"error": {**failure(error), "violations": details.get("violations", [])}}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"], "fixes": case["fixes"]}
    check(matches, "repair", actual, expected)


# --- table_cases.json, editor_cases.json -------------------------------------------------------

TABLES = load("table_cases.json")
EDITOR = load("editor_cases.json")


def table_result(kind: str, case: dict[str, Any]) -> Any:
    previous = arg(case["previous"]) if case.get("previous") is not None else None
    if kind == "strip":
        return ops.strip_row_keys(arg(case["rows"]))
    if kind == "ordered":
        return ops.ordered_rows(arg(case["rows"]))
    if kind == "assign":
        return ops.assign_row_ids(arg(case["rows"]), previous)
    if kind == "assign_node":
        return ops.assign_table_row_ids(arg(case["node"]))
    if kind == "assign_changed":
        return ops.assign_changed_table_row_ids(arg(case["base"]), arg(case["target"]))
    if kind == "strip_flow":
        return ops.strip_flow_table_row_keys(arg(case["flow"]))
    raise AssertionError(kind)


@pytest.mark.parametrize(
    ("kind", "case"),
    [
        pytest.param(kind, case, id=f"{kind}::{case['name']}")
        for kind in ("strip", "ordered", "assign", "assign_node", "assign_changed", "strip_flow")
        for case in TABLES[kind]
    ],
)
def test_table_case(kind, case):
    check(matches, kind, table_result(kind, case), case["expected"])


@pytest.mark.parametrize("case", section("table_cases.json", "fill_positions"))
def test_fill_positions(case):
    # The binding fills positions as part of assigning row ids. Rows that
    # already have unique ids show only the positions it filled.
    rows = case["rows"]
    assigned = ops.assign_row_ids(arg([{**row, "__id__": f"row{index}"} for index, row in enumerate(rows)]))
    positions = [row.get("__pos__") for row in assigned]
    check(matches, "positions", positions, [row.get("__pos__") for row in case["expected"]])


@pytest.mark.parametrize("case", section("editor_cases.json", "assign"))
def test_editor_assign(case):
    previous = arg(case["previous"]) if "previous" in case else None
    check(matches, "rows", ops.assign_row_ids(arg(case["rows"]), previous, editor=True), case["expected"])


@pytest.mark.parametrize("case", section("editor_cases.json", "append"))
def test_editor_append(case):
    check(matches, "rows", ops.append_table_rows(arg(case["rows"]), arg(case["new_rows"])), case["expected"])


@pytest.mark.parametrize("case", section("editor_cases.json", "assign_nodes"))
def test_editor_assign_nodes(case):
    target = ops.assign_changed_table_row_ids(
        arg({"nodes": case["previous"]}), arg({"nodes": case["nodes"]}), editor=True
    )
    check(matches, "nodes", target["nodes"], case["expected"])


@pytest.mark.parametrize("case", section("editor_cases.json", "edge_fixes"))
def test_edge_fixes(case):
    check(matches, "fixes", ops.edge_fixes(arg(case["read"]), arg(case["shown"])), case["fixes"])


@pytest.mark.parametrize("case", section("editor_cases.json", "fixes_for_edges"))
def test_fixes_for_edges(case):
    check(matches, "fixes", ops.fixes_for_edges(arg(case["fixes"]), arg(case["edge_ids"])), case["expected"])


# --- backward_cases.json --------------------------------------------------------------------------


def unordered(lists: list[Any]) -> list[Any]:
    keys = {"delete_nodes": "ids", "delete_edges": "ids", "add_nodes": "nodes", "add_edges": "edges"}
    out = []
    for operations in lists:
        normalized = []
        for operation in operations:
            key = keys.get(operation["type"])
            if key:
                items = sorted(operation[key], key=lambda item: item if isinstance(item, str) else item["id"])
                normalized.append({**operation, key: items})
            else:
                normalized.append(operation)
        out.append(normalized)
    return out


@pytest.mark.parametrize("case", section("backward_cases.json", "cases"))
def test_backward_case(case):
    state = ops.GraphState(arg(case["base"]))
    applied = state.apply(arg(case["operations"]), backward=True)
    check(matches, "backward operations", unordered(applied["backward_operations"]), unordered(case["backward"]))
    for backward in reversed(applied["backward_operations"]):
        state.apply(backward, mode="preview")
    assert ops.graphs_equal(state.to_json().encode(), arg(case["base"]))


@pytest.mark.parametrize("case", section("backward_cases.json", "undo"))
def test_undo_case(case):
    state = ops.GraphState(arg(case["base"]))
    applied = state.apply(arg(case["operations"]), backward=True)
    undo = [operation for backward in reversed(applied["backward_operations"]) for operation in backward]
    check(matches, "undo", unordered([undo]), unordered([case["undo"]]))
    state.apply(undo)
    assert ops.graphs_equal(state.to_json().encode(), arg(case["base"]))


# --- restore_cases.json, write_cases.json ------------------------------------------------------------


@pytest.mark.parametrize("case", section("restore_cases.json", "cases"))
def test_restore(case):
    try:
        actual = {"expected": ops.apply_restore_fixes(arg(case["revision"]), arg(case["stored"]), arg(case["fixes"]))}
    except ops.EngineError as error:
        actual = {"error": failure(error)}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"]}
    check(strict, "restored revision", actual, expected)


@pytest.mark.parametrize("case", section("write_cases.json", "cases"))
def test_write(case):
    try:
        prepared = ops.prepare_write(arg(case["stored"]), arg(case["target"]), arg(case["options"]))
        # A graph comes back only when the save changed it; the caller has the others.
        for key, given in (("base", case["stored"]), ("target", case["target"])):
            assert key not in prepared or prepared[key] != plain(given), f"{key} comes back unchanged"
        actual = {"expected": {"base": case["stored"], "target": case["target"], **prepared}}
    except ops.EngineError as error:
        details = error.details
        actual = {"error": {"graph": details.get("graph"), "violations": details.get("violations")}}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"]}
    check(matches, "prepared write", actual, expected)


RULE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@pytest.mark.parametrize("name", sorted(path.name for path in FIXTURES.glob("*.json")))
def test_every_case_names_its_rule(name):
    """Every case names the rule it checks; fixtures/README.md lists the rules."""
    missing = [
        f"{section}: {case.get('name', index)}"
        for section, cases in load(name).items()
        if isinstance(cases, list)
        for index, case in enumerate(cases)
        if isinstance(case.get("rule"), Number) or not RULE.fullmatch(case.get("rule") or "")
    ]
    assert not missing, f"{name}: cases without a rule: {missing}"


def test_every_fixture_file_is_run():
    run = {
        "apply_cases.json",
        "merge_cases.json",
        "property_cases.json",
        "diff_cases.json",
        "canonical_cases.json",
        "validation_cases.json",
        "repair_cases.json",
        "table_cases.json",
        "editor_cases.json",
        "backward_cases.json",
        "restore_cases.json",
        "write_cases.json",
        "limit_cases.json",
    }
    assert {path.name for path in FIXTURES.glob("*.json")} == run
