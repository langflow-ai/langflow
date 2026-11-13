"""Compare the Rust engine with the Python engine on real flows.

For every ``starter_projects/*.json`` under the given folder, this checks that
both engine objects (``lfx.services.flow_operations.engine``) agree on the
graph hash, the violations (as stored, and as a new flow), the repair fixes,
the derived operations from an empty flow and to edited copies, with the
functions and with ``GraphPlain``, and the graph hash after applying those
operations one at a time and replaying their forward operations. Run it with
both ``lfx`` and ``lfx_native`` importable:

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

from lfx.services.flow_operations.engine import PythonEngine, RustEngine
from lfx.services.flow_operations.exceptions import FlowOperationError

EMPTY = {"nodes": [], "edges": []}
# How often an edited copy changes each kind of thing.
VALUE_EDIT = 0.1
ADVANCED_TOGGLE = 0.12
SHOW_TOGGLE = 0.13
MOVE = 0.2
HIDE_OUTPUT = 0.1
DROP_NODE = 0.5


def outcome(run: Any) -> Any:
    """What a call returns, or the kind and code of the engine error it raises."""
    try:
        return run()
    except FlowOperationError as error:
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
    checks = 0

    def check(what: str, run: Any) -> None:
        """Run ``run(engine)`` on both engine objects; both must give the same outcome."""
        nonlocal checks
        checks += 1
        python, rust = outcome(lambda: run(PythonEngine)), outcome(lambda: run(RustEngine))
        if python != rust:
            differences.append(f"{path.name}: {what}: {str(python)[:300]} != {str(rust)[:300]}")

    check("graph hash", lambda engine: engine.graph_hash(data))
    check("violations", lambda engine: engine.validate(data))
    check("violations as a new flow", lambda engine: engine.validate(data, EMPTY))
    check("repair fixes as a new flow", lambda engine: engine.repair(data, EMPTY)["fixes"])
    check(
        "plain graph save as a new flow",
        lambda engine: engine.GraphPlain(data).validate(engine.GraphPlain(EMPTY)),
    )
    rng = random.Random(path.name)  # noqa: S311 - reproducible edits, not secrets
    pairs = [("from an empty flow", EMPTY, data)] + [(f"to edit {n}", data, edited(data, rng)) for n in range(4)]
    for label, base, target in pairs:
        check(f"derived operations {label}", lambda engine: engine.ops_diff(base, target))  # noqa: B023
        check(
            f"plain graph diff {label}",
            lambda engine: engine.GraphPlain(base).ops_diff(engine.GraphPlain(target)),  # noqa: B023
        )
        operations = outcome(lambda: PythonEngine.ops_diff(base, target))  # noqa: B023
        if not isinstance(operations, list):
            continue

        def replayed(engine: Any) -> str:
            """The graph hash after applying the operations one at a time, then replaying them, on one state."""
            state = engine.GraphState(base)  # noqa: B023
            forward = [state.apply([operation], forward=True)["forward_operations"] for operation in operations]  # noqa: B023
            replay_state = engine.GraphState(base)  # noqa: B023
            for batch in forward:
                replay_state.replay(batch)
            return engine.graph_hash(state.to_dict()), engine.graph_hash(replay_state.to_json().encode())

        check(f"applied and replayed graph hash {label}", replayed)
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
