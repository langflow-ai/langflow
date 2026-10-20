"""Check the Python engine against the shared fixtures.

The fixture files are the specification of the engine: their expected outputs
are reviewed data, and every engine must meet them. This script runs the
Python engine of the operation log stack (``lfx.services.flow_operations``,
and the restore fix check and the save path of ``langflow.services.flow_history``)
over the inputs of every case. It reports each case whose result differs from
the expected output, with the case's name and rule. It never writes a fixture
file. Run it from the repository root of a checkout of the stack's top branch
(``oplog-history-ui``), with ``lfx`` and ``langflow`` importable:

    uv run python src/lfx-native/fixtures/tools/check.py

It exits with 1 when a case differs. It does not check what the Python engine
does not have: inverses and the editor's table rules and edge fixes
(``inverse_cases.json`` and ``editor_cases.json``, which ``check_editor.mjs``
checks).
"""

from __future__ import annotations

import copy
import json
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from langflow.services.flow_history.errors import RestoreFixNotAllowedError
from langflow.services.flow_history.recorder import normalize_absent_graph
from langflow.services.flow_history.restore_fixes import apply_restore_fixes
from lfx.services.flow_operations import (
    FlowDataValidationError,
    FlowOperationError,
    apply_flow_operations,
    assign_changed_table_row_ids,
    assign_row_ids,
    assign_table_row_ids,
    canonical_json,
    derive_flow_operations,
    diff_flow_data,
    dump_flow_operation,
    find_graph_violations,
    graph_hash,
    graphs_equal,
    load_node_schema,
    ordered_rows,
    parse_flow_operations,
    parse_handle,
    repair_flow_data,
    strip_flow_table_row_keys,
    strip_row_keys,
    values_equal,
)
from lfx.services.flow_operations.table_rows import fill_missing_positions

FIXTURES = Path(__file__).resolve().parent.parent
GENERATED_EDGE_ID = "<generated edge id>"
GENERATED_ROW_ID = "<generated row id>"


class Difference(Exception):  # noqa: N818 - a case result, not a failure of this script
    """What a case expects and what the engine gave instead."""

    def __init__(self, what: str, actual: Any, expected: Any) -> None:
        super().__init__(what)
        self.what = what
        self.actual = actual
        self.expected = expected


# --- Comparison ---------------------------------------------------------------------------------


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def strict(actual: Any, expected: Any) -> bool:
    """Equal as JSON: objects in any key order, numbers by their type and value."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(strict(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(strict(a, b) for a, b in zip(actual, expected, strict=True))
    return type(actual) is type(expected) and actual == expected


def matches(actual: Any, expected: Any) -> bool:
    """Equal as JSON, numbers by value, and a generated-id placeholder matching any id of its shape."""
    if expected == GENERATED_EDGE_ID:
        return isinstance(actual, str) and re.fullmatch(r"e-[0-9A-Za-z]{21}", actual) is not None
    if expected == GENERATED_ROW_ID:
        return isinstance(actual, str) and re.fullmatch(r"[0-9A-Za-z]{10}", actual) is not None
    if _number(actual) and _number(expected):
        return float(actual) == float(expected)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(matches(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(matches(a, b) for a, b in zip(actual, expected, strict=True))
    return type(actual) is type(expected) and actual == expected


def check(compare: Callable[[Any, Any], bool], what: str, actual: Any, expected: Any) -> None:
    if not compare(actual, expected):
        raise Difference(what, actual, expected)


def holds(what: str, condition: bool) -> None:  # noqa: FBT001
    if not condition:
        raise Difference(what, actual=False, expected=True)


def _error(exc: Exception) -> dict[str, Any]:
    return {"error": type(exc).__name__, "code": exc.code}


def _fresh(value: Any) -> Any:
    return copy.deepcopy(value)


def _graph(case: dict[str, Any], key: str) -> Any:
    """A case's graph: its ``<key>_json`` text when it has one, read as Python reads it, or its ``<key>``."""
    return json.loads(case[f"{key}_json"]) if f"{key}_json" in case else case.get(key)


# --- apply_cases.json, merge_cases.json, property_cases.json ----------------------------------------


def _ignoring_id_order(operations: list[dict]) -> list[dict]:
    return [
        {**operation, "ids": sorted(operation["ids"])}
        if operation["type"] in {"delete_nodes", "delete_edges"}
        else operation
        for operation in operations
    ]


def _ignoring_row_order(flow_data: Any) -> Any:
    flow_data = _fresh(flow_data)
    schema = load_node_schema()
    for node in flow_data.get("nodes", []):
        for name, field in node.get("data", {}).get("node", {}).get("template", {}).items():
            path = ("data", "node", "template", name, "value")
            rows = field.get("value") if isinstance(field, dict) else None
            if isinstance(rows, list) and schema.keyed_list_at(node, path) is schema.table:
                field["value"] = sorted(rows, key=lambda row: row["__id__"])
    return flow_data


def apply_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    base = _fresh(case["base"])
    try:
        result = apply_flow_operations(base, parse_flow_operations(_fresh(case["operations"])))
    except FlowOperationError as exc:
        check(strict, "error", _error(exc), {"error": case.get("error"), "code": case.get("code")})
        check(strict, "base after the refused batch", base, case["base"])
        return
    holds("the operations are refused", "error" not in case)
    check(strict, "flow data", _ignoring_row_order(result.flow_data), _ignoring_row_order(case["expected"]))
    check(
        strict,
        "forward operations",
        _ignoring_id_order([dump_flow_operation(op) for op in result.forward_ops]),
        _ignoring_id_order(case.get("forward_operations", case["operations"])),
    )


def merge_case(case: dict[str, Any], document: dict[str, Any]) -> None:
    graph = _fresh(document["base"])
    outcomes: dict[str, Any] = {}
    for name in case["order"]:
        before = _fresh(graph)
        try:
            graph = apply_flow_operations(graph, parse_flow_operations(_fresh(case["transactions"][name]))).flow_data
        except FlowOperationError as exc:
            check(strict, f"graph after refusing {name}", graph, before)
            outcomes[name] = _error(exc)
        else:
            outcomes[name] = "applied"
    check(strict, "outcomes", outcomes, case["outcomes"])
    holds("the final graph equals expected", graphs_equal(graph, case["expected"]))


def property_sequence(sequence: dict[str, Any], document: dict[str, Any]) -> None:
    graph = _fresh(document["base"])
    for index, transaction in enumerate(sequence["transactions"]):
        try:
            graph = apply_flow_operations(graph, parse_flow_operations(_fresh(transaction))).flow_data
        except FlowOperationError as exc:
            what = f"transaction {index + 1}"
            raise Difference(what, _error(exc), "applied") from exc
    check(strict, "graph hash", graph_hash(graph), sequence["graph_hash"])


# --- diff_cases.json ------------------------------------------------------------------------------


def diff_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    base, target = _fresh(case["base"]), _fresh(case["target"])
    operations = [dump_flow_operation(operation) for operation in diff_flow_data(base, target)]
    check(strict, "operations", operations, case["operations"])
    holds("the derived graph equals the target", graphs_equal(derive_flow_operations(base, target).flow_data, target))
    graph = _fresh(case["base"])
    for operation in parse_flow_operations(_fresh(case["operations"])):
        graph = apply_flow_operations(graph, [operation]).flow_data
    holds("the operations replay to the target", graphs_equal(graph, case["target"]))


# --- canonical_cases.json, limit_cases.json --------------------------------------------------------


def canonical_text(case: dict[str, Any], _document: dict[str, Any]) -> None:
    try:
        actual: dict[str, Any] = {"canonical": canonical_json(json.loads(case["json"]))}
    except FlowDataValidationError as exc:
        actual = {"error": _error(exc)}
    expected = {"error": case["error"]} if "error" in case else {"canonical": case["canonical"]}
    check(strict, "canonical form", actual, expected)


def equality_sample(left: dict[str, Any], document: dict[str, Any]) -> None:
    for index, right in enumerate(document["equality_samples"]):
        equal = values_equal(json.loads(left["json"]), json.loads(right["json"]))
        check(strict, f"equality with sample #{index}", equal, left["canonical"] == right["canonical"])


def graph_comparison(case: dict[str, Any], _document: dict[str, Any]) -> None:
    check(strict, "equal", graphs_equal(case["left"], case["right"]), case["equal"])
    check(strict, "left hash", graph_hash(case["left"]), case["left_hash"])
    check(strict, "right hash", graph_hash(case["right"]), case["right_hash"])


def handle_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    check(strict, "parsed handle", parse_handle(case["handle"]), case["parsed"])


# --- validation_cases.json, repair_cases.json ------------------------------------------------------


def validation_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    try:
        violations = find_graph_violations(
            _graph(case, "flow"), check_values=case.get("check_values", True), base=case.get("base")
        )
        actual: dict[str, Any] = {"violations": [violation.to_dict() for violation in violations]}
    except FlowOperationError as exc:
        actual = {"error": _error(exc)}
    expected = {"error": case["error"]} if "error" in case else {"violations": case["violations"]}
    check(strict, "violations", actual, expected)


def repair_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    try:
        result = repair_flow_data(_fresh(_graph(case, "flow")), base=case.get("base"))
        actual: dict[str, Any] = {"expected": result.flow_data, "fixes": [fix.to_dict() for fix in result.fixes]}
    except FlowDataValidationError as exc:
        actual = {"error": {**_error(exc), "violations": [v.to_dict() for v in exc.violations]}}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"], "fixes": case["fixes"]}
    check(matches, "repair", actual, expected)


# --- table_cases.json ------------------------------------------------------------------------------


def _assign_node(case: dict[str, Any]) -> Any:
    node = _fresh(case["node"])
    assign_table_row_ids(node)
    return node


TABLE_RUNS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "strip": lambda case: strip_row_keys(_fresh(case["rows"])),
    "ordered": lambda case: ordered_rows(_fresh(case["rows"])),
    "assign": lambda case: assign_row_ids(_fresh(case["rows"]), _fresh(case.get("previous"))),
    "assign_node": _assign_node,
    "assign_changed": lambda case: assign_changed_table_row_ids(_fresh(case["base"]), _fresh(case["target"])),
    "strip_flow": lambda case: strip_flow_table_row_keys(_fresh(case["flow"])),
}


def table_case(section: str) -> Callable[[dict[str, Any], dict[str, Any]], None]:
    def run(case: dict[str, Any], _document: dict[str, Any]) -> None:
        check(matches, section, TABLE_RUNS[section](case), case["expected"])

    return run


def fill_positions(case: dict[str, Any], _document: dict[str, Any]) -> None:
    rows = _fresh(case["rows"])
    filled = fill_missing_positions(rows)
    expected = {"expected": case["expected"], "filled": case["filled"]}
    check(matches, "positions", {"expected": rows, "filled": filled}, expected)


# --- restore_cases.json, write_cases.json -----------------------------------------------------------


def restore_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    try:
        fixes = parse_flow_operations(_fresh(case["fixes"]))
        revision = apply_restore_fixes(_fresh(case["revision"]), _fresh(case["stored"]), fixes)
        actual: dict[str, Any] = {"expected": revision}
    except (RestoreFixNotAllowedError, FlowOperationError) as exc:
        actual = {"error": _error(exc)}
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"]}
    check(strict, "restored revision", actual, expected)


def _prepare_write(stored: Any, target: Any, options: dict[str, Any]) -> dict[str, Any]:
    """The engine's part of the recorder's write path, composed from the Python engine as write_flow_graph runs it."""
    repairs: list[dict[str, Any]] = []
    stored_repaired = False
    if options["started"]:
        base = stored
    else:
        base = normalize_absent_graph(stored)
        violations = find_graph_violations(base)
        if violations:
            if not options["repair_invalid_graph"]:
                return {"error": {"graph": "stored", "violations": [v.to_dict() for v in violations]}}
            repaired = repair_flow_data(base)
            base = repaired.flow_data
            stored_repaired = True
            repairs += [{"graph": "stored", **fix.to_dict()} for fix in repaired.fixes]
    target = normalize_absent_graph(target)
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
    return {
        "expected": {
            "base": base,
            "stored_repaired": stored_repaired,
            "target": target,
            "repairs": repairs,
            "operations": [dump_flow_operation(operation) for operation in derived.operations],
        }
    }


def write_case(case: dict[str, Any], _document: dict[str, Any]) -> None:
    actual = _prepare_write(_fresh(case["stored"]), _fresh(case["target"]), case["options"])
    expected = {"error": case["error"]} if "error" in case else {"expected": case["expected"]}
    check(matches, "prepared write", actual, expected)


# --- Running every case ------------------------------------------------------------------------------

Run = Callable[[dict[str, Any], dict[str, Any]], None]

CHECKS: list[tuple[str, str, Run]] = [
    ("apply_cases.json", "cases", apply_case),
    ("merge_cases.json", "cases", merge_case),
    ("property_cases.json", "sequences", property_sequence),
    ("diff_cases.json", "cases", diff_case),
    ("canonical_cases.json", "numbers", canonical_text),
    ("canonical_cases.json", "values", canonical_text),
    ("canonical_cases.json", "equality_samples", equality_sample),
    ("canonical_cases.json", "graphs", graph_comparison),
    ("canonical_cases.json", "handles", handle_case),
    ("limit_cases.json", "refused", canonical_text),
    ("limit_cases.json", "accepted", canonical_text),
    ("validation_cases.json", "cases", validation_case),
    ("repair_cases.json", "cases", repair_case),
    *[("table_cases.json", section, table_case(section)) for section in TABLE_RUNS],
    ("table_cases.json", "fill_positions", fill_positions),
    ("restore_cases.json", "cases", restore_case),
    ("write_cases.json", "cases", write_case),
]


def differences(document: dict[str, Any], name: str, section: str, run: Run) -> Iterator[str]:
    for index, case in enumerate(document[section]):
        label = f"{name} {section} {json.dumps(case.get('name', f'#{index}'), ensure_ascii=False)}"
        rule = case.get("rule")
        if not isinstance(rule, str) or not rule:
            yield f"{label}: the case names no rule"
            continue
        try:
            run(case, document)
        except Difference as difference:
            yield (
                f"{label} (rule {rule}): {difference.what} differs\n"
                f"  engine:   {json.dumps(difference.actual, ensure_ascii=False)}\n"
                f"  expected: {json.dumps(difference.expected, ensure_ascii=False)}"
            )
        except Exception as exc:  # noqa: BLE001 - every case is reported, whatever the engine raises
            yield f"{label} (rule {rule}): the engine raised {type(exc).__name__}: {exc}"


def main() -> int:
    found = 0
    for name, section, run in CHECKS:
        document = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        reported = list(differences(document, name, section, run))
        for line in reported:
            print(line)
        print(f"{name} {section}: {len(document[section])} cases, {len(reported)} differences")
        found += len(reported)
    print(f"the Python engine: {found} differences")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
