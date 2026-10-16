"""Compare the Rust engine with the Python engine on real flows.

For every ``starter_projects/*.json`` under the given folder, this checks that
both engines agree on the graph hash, the violations (as stored, and as a new
flow), the repair fixes, the diff from an empty flow and to edited copies,
the derived operations, and the graph after replaying them one at a time.
Run it with both ``lfx`` (at the reference commit) and ``lfx_native``
importable:

    python src/lfx-native/fixtures/tools/compare_engines.py src

It prints the number of checks and every difference, and exits with 1 when
there is one.
"""

from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path
from typing import Any

from lfx.services.flow_operations import (
    FlowOperationError,
    apply_flow_operations,
    derive_flow_operations,
    diff_flow_data,
    dump_flow_operation,
    find_graph_violations,
    graph_hash,
    parse_flow_operations,
    repair_flow_data,
)
from lfx_native import ops

EMPTY = {"nodes": [], "edges": []}
# How often an edited copy changes each kind of thing.
VALUE_EDIT = 0.1
ADVANCED_TOGGLE = 0.12
SHOW_TOGGLE = 0.13
MOVE = 0.2
HIDE_OUTPUT = 0.1
DROP_NODE = 0.5


def python_outcome(run: Any) -> Any:
    try:
        return run()
    except FlowOperationError as error:
        return {"error": type(error).__name__, "code": error.code}


def rust_outcome(run: Any) -> Any:
    try:
        return run()
    except ops.EngineError as error:
        return {"error": error.kind, "code": error.code}


def edited(graph: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """A copy of a graph with random value, toggle, position and output edits, and maybe a node fewer."""
    graph = copy.deepcopy(graph)
    for node in graph["nodes"]:
        body = node.get("data", {}).get("node", {})
        for name, field in body.get("template", {}).items():
            if not isinstance(field, dict):
                continue
            roll = rng.random()
            if roll < VALUE_EDIT and isinstance(field.get("value"), str):
                field["value"] += " edited"
            elif roll < ADVANCED_TOGGLE:
                field["advanced"] = not field.get("advanced", False)
            elif roll < SHOW_TOGGLE and name != "code":
                field["show"] = not field.get("show", True)
        if rng.random() < MOVE:
            node.setdefault("position", {})["x"] = rng.random() * 1000
        if rng.random() < HIDE_OUTPUT and body.get("outputs"):
            body["outputs"][0]["hidden"] = True
    if graph["nodes"] and rng.random() < DROP_NODE:
        graph["nodes"].pop(rng.randrange(len(graph["nodes"])))
        ids = {node["id"] for node in graph["nodes"]}
        graph["edges"] = [edge for edge in graph["edges"] if edge["source"] in ids and edge["target"] in ids]
    return graph


def compare(path: Path, differences: list[str]) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))["data"]
    text = json.dumps(data)
    checks = 0

    def check(what: str, python: Any, rust: Any) -> None:
        nonlocal checks
        checks += 1
        if python != rust:
            differences.append(f"{path.name}: {what}: {str(python)[:300]} != {str(rust)[:300]}")

    check("graph hash", graph_hash(data), ops.graph_hash(text))
    check("violations", [v.to_dict() for v in find_graph_violations(data)], json.loads(ops.validate(text)))
    check(
        "violations as a new flow",
        python_outcome(lambda: [v.to_dict() for v in find_graph_violations(data, base=EMPTY)]),
        rust_outcome(lambda: json.loads(ops.validate(text, json.dumps(EMPTY)))),
    )
    check(
        "repair fixes as a new flow",
        python_outcome(lambda: [fix.to_dict() for fix in repair_flow_data(data, base=EMPTY).fixes]),
        rust_outcome(lambda: json.loads(ops.repair(text, json.dumps(EMPTY)))["fixes"]),
    )
    rng = random.Random(path.name)  # noqa: S311 - reproducible edits, not secrets
    pairs = [("from an empty flow", EMPTY, data)] + [(f"to edit {n}", data, edited(data, rng)) for n in range(4)]
    for label, base, target in pairs:
        base_text, target_text = json.dumps(base), json.dumps(target)
        operations = python_outcome(lambda: [dump_flow_operation(o) for o in diff_flow_data(base, target)])  # noqa: B023
        check(f"diff {label}", operations, rust_outcome(lambda: json.loads(ops.diff(base_text, target_text))))  # noqa: B023
        if not isinstance(operations, list):
            continue
        derived = derive_flow_operations(base, target)
        rust_derived = json.loads(ops.derive(base_text, target_text))
        check(
            f"derived operations {label}",
            [dump_flow_operation(o) for o in derived.operations],
            rust_derived["operations"],
        )
        graph, state = base, ops.GraphState(base_text)
        for operation in operations:
            graph = apply_flow_operations(graph, parse_flow_operations([operation])).flow_data
            state.apply(json.dumps([operation]))
        check(f"replayed graph hash {label}", graph_hash(graph), ops.graph_hash(state.to_json()))
    return checks


def main() -> None:
    files = sorted(Path(sys.argv[1]).rglob("starter_projects/*.json"))
    differences: list[str] = []
    checks = sum(compare(path, differences) for path in files)
    print(f"{len(files)} flows, {checks} checks, {len(differences)} differences")
    for difference in differences:
        print(" -", difference)
    sys.exit(1 if differences else 0)


if __name__ == "__main__":
    main()
