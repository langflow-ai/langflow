"""Every shared fixture file, run through the Python binding.

The fixtures are the engine's specification; the Rust runner and the browser
binding's runner run the same files with the same checks. Numbers keep their
original text through the binding, so fixtures are read with each number as
its text, and compared as text where the Rust runner compares text.
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


def dump(value: Any) -> str:
    """JSON text of a value read by ``parse``, with every number as it was written."""
    if isinstance(value, Number):
        return str(value)
    if value is None or isinstance(value, (bool, str)):
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
    if isinstance(actual, Number) and isinstance(expected, Number):
        return float(actual) == float(expected)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(matches(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(matches(a, b) for a, b in zip(actual, expected, strict=True))
    return type(actual) is type(expected) and actual == expected


def check(compare: Callable[[Any, Any], bool], what: str, actual: Any, expected: Any) -> None:
    assert compare(actual, expected), f"{what} differs\n  actual:   {dump(actual)}\n  expected: {dump(expected)}"


def failure(error: ops.EngineError) -> dict[str, Any]:
    return {"error": error.kind, "code": error.code}


def graph_text(case: dict[str, Any], key: str) -> str:
    """A case's graph as JSON text: its exact ``<key>_json`` text when it has one."""
    return case[f"{key}_json"] if f"{key}_json" in case else dump(case.get(key))


# --- apply_cases.json, merge_cases.json, property_cases.json ------------------------------


def ignoring_id_order(operations: list[Any]) -> list[Any]:
    return [
        {**operation, "ids": sorted(operation["ids"])}
        if operation["type"] in {"delete_nodes", "delete_edges"}
        else operation
        for operation in operations
    ]


def ignoring_row_order(flow: Any) -> Any:
    flow = parse(dump(flow))
    for node in flow.get("nodes", []):
        node_text = dump(node)
        for name in parse(ops.table_fields(node_text)):
            field = node["data"]["node"]["template"][name]
            field["value"] = sorted(field["value"], key=lambda row: row["__id__"])
    return flow


@pytest.mark.parametrize("case", section("apply_cases.json", "cases"))
def test_apply_case(case):
    try:
        state = ops.GraphState(dump(case["base"]))
    except ops.EngineError as error:
        check(strict, "error", failure(error), {"error": case.get("error"), "code": case.get("code")})
        return
    try:
        applied = parse(state.apply(dump(case["operations"]), forward=True))
    except ops.EngineError as error:
        check(strict, "error", failure(error), {"error": case.get("error"), "code": case.get("code")})
        check(strict, "state after the refused batch", parse(state.to_json()), case["base"])
        return
    assert "error" not in case, "expected the operations to be refused"
    check(strict, "flow data", ignoring_row_order(parse(state.to_json())), ignoring_row_order(case["expected"]))
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
    state = ops.GraphState(dump(DOCUMENT["base"]))
    outcomes = {}
    for name in case["order"]:
        before = parse(state.to_json())
        try:
            state.apply(dump(case["transactions"][name]))
        except ops.EngineError as error:
            check(strict, f"state after refusing {name}", parse(state.to_json()), before)
            outcomes[name] = failure(error)
        else:
            outcomes[name] = "applied"
    check(strict, "outcomes", outcomes, case["outcomes"])
    assert ops.graphs_equal(state.to_json(), dump(case["expected"]))


PROPERTY = load("property_cases.json")


@pytest.mark.parametrize("sequence", section("property_cases.json", "sequences"))
def test_property_sequence(sequence):
    state = ops.GraphState(dump(PROPERTY["base"]))
    for transaction in sequence["transactions"]:
        state.apply(dump(transaction))
    assert ops.graph_hash(state.to_json()) == sequence["graph_hash"]


# --- diff_cases.json --------------------------------------------------------------------------


@pytest.mark.parametrize("case", section("diff_cases.json", "cases"))
def test_diff_case(case):
    base, target = dump(case["base"]), dump(case["target"])
    check(strict, "operations", parse(ops.diff(base, target)), case["operations"])
    assert ops.graphs_equal(dump(parse(ops.derive(base, target))["flow_data"]), target)
    state = ops.GraphState(base)
    for operation in case["operations"]:
        state.apply(dump([operation]))
    assert ops.graphs_equal(state.to_json(), target)


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
        actual = {"canonical": ops.canonical_json(case["json"])}
    except ops.EngineError as error:
        actual = {"error": failure(error)}
    expected = {"error": case["error"]} if "error" in case else {"canonical": case["canonical"]}
    check(strict, "canonical form", actual, expected)


def test_equality_samples():
    samples = load("canonical_cases.json")["equality_samples"]
    for left in samples:
        for right in samples:
            assert ops.values_equal(left["json"], right["json"]) == (left["canonical"] == right["canonical"])


@pytest.mark.parametrize("case", section("canonical_cases.json", "graphs"))
def test_graph_comparison(case):
    left, right = dump(case["left"]), dump(case["right"])
    assert ops.graphs_equal(left, right) == case["equal"]
    assert ops.graph_hash(left) == case["left_hash"]
    assert ops.graph_hash(right) == case["right_hash"]


# --- validation_cases.json, repair_cases.json -------------------------------------------------


@pytest.mark.parametrize("case", section("validation_cases.json", "cases"))
def test_validation_case(case):
    base = dump(case["base"]) if "base" in case else None
    try:
        actual = {
            "violations": parse(
                ops.validate(graph_text(case, "flow"), base, check_values=case.get("check_values", True))
            )
        }
    except ops.EngineError as error:
        actual = {"error": failure(error)}
    expected = {"error": case["error"]} if "error" in case else {"violations": case["violations"]}
    check(strict, "violations", actual, expected)


@pytest.mark.parametrize("case", section("repair_cases.json", "cases"))
def test_repair_case(case):
    base = dump(case["base"]) if "base" in case else None
    try:
        repaired = parse(ops.repair(graph_text(case, "flow"), base))
        actual = {"expected": repaired["flow_data"], "fixes": repaired["fixes"]}
    except ops.EngineError as error:
        details = parse(error.details)
        actual = {"error": {**failure(error), "violations": details.get("violations", [])}}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"], "fixes": case["fixes"]}
    check(matches, "repair", actual, expected)


# --- table_cases.json, editor_cases.json -------------------------------------------------------

TABLES = load("table_cases.json")
EDITOR = load("editor_cases.json")


def table_result(kind: str, case: dict[str, Any]) -> Any:
    previous = dump(case["previous"]) if case.get("previous") is not None else None
    if kind == "strip":
        return parse(ops.strip_row_keys(dump(case["rows"])))
    if kind == "ordered":
        return parse(ops.ordered_rows(dump(case["rows"])))
    if kind == "assign":
        return parse(ops.assign_row_ids(dump(case["rows"]), previous))
    if kind == "assign_node":
        return parse(ops.assign_table_row_ids(dump(case["node"])))
    if kind == "assign_changed":
        return parse(ops.assign_changed_table_row_ids(dump(case["base"]), dump(case["target"])))
    if kind == "strip_flow":
        return parse(ops.strip_flow_table_row_keys(dump(case["flow"])))
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
    assigned = parse(ops.assign_row_ids(dump([{**row, "__id__": f"row{index}"} for index, row in enumerate(rows)])))
    positions = [row.get("__pos__") for row in assigned]
    check(matches, "positions", positions, [row.get("__pos__") for row in case["expected"]])


@pytest.mark.parametrize("case", section("editor_cases.json", "assign"))
def test_editor_assign(case):
    previous = dump(case["previous"]) if "previous" in case else None
    check(matches, "rows", parse(ops.assign_row_ids(dump(case["rows"]), previous, editor=True)), case["expected"])


@pytest.mark.parametrize("case", section("editor_cases.json", "append"))
def test_editor_append(case):
    check(matches, "rows", parse(ops.append_table_rows(dump(case["rows"]), dump(case["new_rows"]))), case["expected"])


@pytest.mark.parametrize("case", section("editor_cases.json", "assign_nodes"))
def test_editor_assign_nodes(case):
    target = parse(
        ops.assign_changed_table_row_ids(dump({"nodes": case["previous"]}), dump({"nodes": case["nodes"]}), editor=True)
    )
    check(matches, "nodes", target["nodes"], case["expected"])


@pytest.mark.parametrize("case", section("editor_cases.json", "edge_fixes"))
def test_edge_fixes(case):
    check(matches, "fixes", parse(ops.edge_fixes(dump(case["read"]), dump(case["shown"]))), case["fixes"])


@pytest.mark.parametrize("case", section("editor_cases.json", "fixes_for_edges"))
def test_fixes_for_edges(case):
    check(matches, "fixes", parse(ops.fixes_for_edges(dump(case["fixes"]), dump(case["edge_ids"]))), case["expected"])


# --- inverse_cases.json ---------------------------------------------------------------------------


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


@pytest.mark.parametrize("case", section("inverse_cases.json", "cases"))
def test_inverse_case(case):
    state = ops.GraphState(dump(case["base"]))
    applied = parse(state.apply(dump(case["operations"]), inverse=True))
    check(matches, "inverse operations", unordered(applied["inverse_operations"]), unordered(case["inverse"]))
    for inverse in reversed(applied["inverse_operations"]):
        state.apply(dump(inverse), restoring=True)
    assert ops.graphs_equal(state.to_json(), dump(case["base"]))


# --- restore_cases.json, write_cases.json ------------------------------------------------------------


@pytest.mark.parametrize("case", section("restore_cases.json", "cases"))
def test_restore(case):
    try:
        actual = {
            "expected": parse(
                ops.apply_restore_fixes(dump(case["revision"]), dump(case["stored"]), dump(case["fixes"]))
            )
        }
    except ops.EngineError as error:
        actual = {"error": failure(error)}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"]}
    check(strict, "restored revision", actual, expected)


@pytest.mark.parametrize("case", section("write_cases.json", "cases"))
def test_write(case):
    try:
        actual = {
            "expected": parse(ops.prepare_write(dump(case["stored"]), dump(case["target"]), dump(case["options"])))
        }
    except ops.EngineError as error:
        details = parse(error.details)
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
        "inverse_cases.json",
        "restore_cases.json",
        "write_cases.json",
        "limit_cases.json",
    }
    assert {path.name for path in FIXTURES.glob("*.json")} == run
