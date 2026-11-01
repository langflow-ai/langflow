"""Time the Python and Rust flow engines on the same large flow, in one process.

Each benchmark gives every engine the same inputs. It runs warm (after a few
runs that are not counted) and reports the median, the 90th percentile, the
fastest and the slowest of many runs, in milliseconds. ``to_json`` is timed as
the ``str`` both engine objects return, and as ``bytes`` (the ``str`` encoded,
as a server writes it). Memory per loaded graph state is measured in a fresh
process per engine, as the growth of the resident set over a few states built
from the graph's JSON text, as a server reads ``flow.data``.

    python src/lfx-native/fixtures/tools/bench_engines.py LARGE_FLOW.json STARTER_PROJECTS_DIR [--engines python,rust]

``LARGE_FLOW.json`` comes from ``large_flow.py``. The results go to standard
output as JSON lines, one per benchmark and engine.

An engine is an adapter (``Adapter``) over one engine object of
``lfx.services.flow_operations.engine``. A script can register another
adapter in ``ADAPTERS`` and call ``main``.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from large_flow import copy_project, load_projects

PASTED_PROJECT = "Hybrid Search RAG"
REVISIONS = 1000
# The whole-flow save edits this many template values.
SAVE_EDITS = 5
# Of every 50 revisions, the 11th deletes an edge and the 12th adds it back; every 10th from the 6th moves a node.
EDGE_DELETE, EDGE_ADD, CYCLE, MOVE_EVERY, MOVE_AT = 10, 11, 50, 10, 5


class Adapter:
    """The calls a benchmark makes, on one engine object."""

    name = "engine"
    # Benchmarks the engine cannot run.
    skips: frozenset[str] = frozenset()

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def build(self, flow: dict[str, Any]) -> Any:
        return self.engine.GraphState(flow)

    def build_text(self, text: bytes) -> Any:
        """A state from the graph's JSON text, as a server reads ``flow.data`` from the database."""
        return self.engine.GraphState(text)

    def apply(self, state: Any, operations: list[Any]) -> Any:
        return state.apply(operations)

    def apply_forward(self, state: Any, operations: list[Any]) -> list[Any]:
        return state.apply(operations, forward=True)["forward_operations"]

    def stage_keep(self, state: Any, operations: list[Any]) -> Any:
        result = state.stage(operations)
        state.keep()
        return result

    def replay(self, state: Any, operations: list[Any]) -> Any:
        return state.replay(operations)

    def to_json(self, state: Any) -> Any:
        return state.to_json()

    def to_json_bytes(self, state: Any) -> bytes:
        return state.to_json().encode()

    def to_dict(self, state: Any) -> Any:
        return state.to_dict()

    def save(self, base: dict[str, Any], target: dict[str, Any]) -> Any:
        """A whole-flow save's checks: read both graphs once, then validate, repair and diff."""
        plain_base = self.engine.GraphPlain(base)
        plain_target = self.engine.GraphPlain(target)
        violations = plain_target.validate(plain_base)
        repaired, fixes = plain_target.repair(plain_base)
        operations = plain_base.ops_diff(repaired)
        return violations, fixes, operations


def _engine_adapter(kind: str) -> Callable[[], Adapter]:
    def make() -> Adapter:
        from lfx.services.flow_operations.engine import get_engine

        adapter = Adapter(get_engine(kind))
        adapter.name = kind
        return adapter

    return make


ADAPTERS: dict[str, Callable[[], Adapter]] = {"python": _engine_adapter("python"), "rust": _engine_adapter("rust")}


# --- Inputs ------------------------------------------------------------------------------------


def set_field(node_id: str, field: str, value: Any) -> list[dict[str, Any]]:
    path = ["data", "node", "template", field, "value"]
    return [{"type": "update_nodes", "updates": [{"id": node_id, "op": "set_field", "path": path, "value": value}]}]


def first_text_field(flow: dict[str, Any]) -> tuple[str, str]:
    """The first node and template field, in graph order, whose value is a string and that no edge enters."""
    entered = {(edge["target"], edge["data"]["targetHandle"].get("fieldName")) for edge in flow["edges"]}
    for node in flow["nodes"]:
        for name, field in node["data"]["node"]["template"].items():
            if isinstance(field, dict) and isinstance(field.get("value"), str) and (node["id"], name) not in entered:
                return node["id"], name
    msg = "the flow has no text field"
    raise ValueError(msg)


class Inputs:
    """Every benchmark's inputs, built once from the large flow."""

    def __init__(self, flow_path: Path, starter_projects: Path) -> None:
        self.text = flow_path.read_bytes()
        self.flow = json.loads(self.text)
        self.node_id, self.field = first_text_field(self.flow)
        self.edge = self.flow["edges"][len(self.flow["edges"]) // 2]
        projects = dict(load_projects(starter_projects))
        nodes, edges = copy_project(projects[PASTED_PROJECT], "pasted", 90_000.0)
        self.paste = [{"type": "add_nodes", "nodes": nodes}, {"type": "add_edges", "edges": edges}]
        self.pasted_ids = [node["id"] for node in nodes]
        self.delete_pasted = [{"type": "delete_nodes", "ids": self.pasted_ids}]
        self.save_target = self._edited()
        # The same save, with an output added without a position: repair gives it one.
        self.save_target_to_repair = self._edited()
        outputs = next(node for node in self.save_target_to_repair["nodes"] if node["data"]["node"].get("outputs"))
        outputs["data"]["node"]["outputs"].append({"name": "added_output", "types": ["Message"]})

    def _edited(self) -> dict[str, Any]:
        """The large flow after a whole-flow save that edits five values, moves a node and deletes an edge."""
        target = json.loads(self.text)
        edited = 0
        for node in target["nodes"]:
            for field in node["data"]["node"]["template"].values():
                if edited < SAVE_EDITS and isinstance(field, dict) and isinstance(field.get("value"), str):
                    field["value"] += " edited"
                    edited += 1
                    break
        target["nodes"][7]["position"]["x"] += 25
        target["edges"].pop(3)
        return target

    def revisions(self, adapter: Adapter) -> list[list[Any]]:
        """1,000 stored revisions: the forward operations of user batches applied one after another."""
        state = adapter.build(self.flow)
        node_ids = [node["id"] for node in self.flow["nodes"]]
        stored = []
        for index in range(REVISIONS):
            if index % CYCLE == EDGE_DELETE:
                batch = [{"type": "delete_edges", "ids": [self.edge["id"]]}]
            elif index % CYCLE == EDGE_ADD:
                batch = [{"type": "add_edges", "edges": [self.edge]}]
            elif index % MOVE_EVERY == MOVE_AT:
                node_id = node_ids[index % len(node_ids)]
                batch = [
                    {
                        "type": "update_nodes",
                        "updates": [
                            {"id": node_id, "op": "set_field", "path": ["position"], "value": {"x": index, "y": 0}}
                        ],
                    }
                ]
            else:
                batch = set_field(self.node_id, self.field, f"revision {index}")
            stored.append(adapter.apply_forward(state, batch))
        return stored


# --- Timing ------------------------------------------------------------------------------------


def measure(
    run: Callable[[], Any], *, runs: int, warmup: int = 3, setup: Callable[[], Any] | None = None
) -> dict[str, Any]:
    """Time ``run`` ``runs`` times after ``warmup`` runs; ``setup`` runs untimed before each run."""
    for _ in range(warmup):
        if setup:
            setup()
        run()
    gc.collect()
    times = []
    for _ in range(runs):
        if setup:
            setup()
        start = time.perf_counter_ns()
        run()
        times.append((time.perf_counter_ns() - start) / 1e6)
    times.sort()
    return {
        "runs": runs,
        "median_ms": round(statistics.median(times), 4),
        "p90_ms": round(times[min(len(times) - 1, int(len(times) * 0.9))], 4),
        "min_ms": round(times[0], 4),
        "max_ms": round(times[-1], 4),
    }


def benchmarks(adapter: Adapter, inputs: Inputs, scale: float = 1.0) -> dict[str, dict[str, Any]]:
    """Every benchmark on one engine. ``scale`` multiplies the number of runs."""

    def runs(count: int) -> int:
        return max(3, int(count * scale))

    results: dict[str, dict[str, Any]] = {}
    flow = inputs.flow

    def bench(name: str, run: Callable[[], Any], count: int, **options: Any) -> None:
        if name in adapter.skips:
            return
        results[name] = measure(run, runs=runs(count), **options)

    bench("build GraphState from a dict", lambda: adapter.build(flow), 20)
    bench("build GraphState from JSON text (bytes)", lambda: adapter.build_text(inputs.text), 20)
    state = adapter.build(flow)
    counter = iter(range(10**9))
    bench(
        "one field write (apply)",
        lambda: adapter.apply(state, set_field(inputs.node_id, inputs.field, f"v{next(counter)}")),
        300,
    )
    bench(
        "stage+keep of one field write",
        lambda: adapter.stage_keep(state, set_field(inputs.node_id, inputs.field, f"v{next(counter)}")),
        300,
    )
    edge = inputs.edge
    adapter.apply(state, [{"type": "delete_edges", "ids": [edge["id"]]}])
    bench(
        "add edge",
        lambda: adapter.apply(state, [{"type": "add_edges", "edges": [edge]}]),
        300,
        # A delete of an edge that is not there records nothing.
        setup=lambda: adapter.apply(state, [{"type": "delete_edges", "ids": [edge["id"]]}]),
    )
    adapter.apply(state, [{"type": "delete_edges", "ids": [edge["id"]]}])
    adapter.apply(state, [{"type": "add_edges", "edges": [edge]}])
    # Each run starts with the section deleted, then with it pasted.
    adapter.apply(state, inputs.paste)
    bench(
        "paste a section (11 nodes, 7 edges)",
        lambda: adapter.apply(state, inputs.paste),
        100,
        setup=lambda: adapter.apply(state, inputs.delete_pasted),
    )
    adapter.apply(state, inputs.delete_pasted)
    bench(
        "delete a pasted section",
        lambda: adapter.apply(state, inputs.delete_pasted),
        100,
        setup=lambda: adapter.apply(state, inputs.paste),
    )
    stored = inputs.revisions(adapter)
    replayed: list[Any] = []

    def replay_all() -> None:
        target = replayed[0]
        for operations in stored:
            adapter.replay(target, operations)

    bench(
        "replay of 1,000 stored revisions",
        replay_all,
        8,
        warmup=1,
        setup=lambda: replayed.__setitem__(slice(None), [adapter.build(flow)]),
    )
    bench("to_json of the graph (str)", lambda: adapter.to_json(state), 30)
    bench("to_json of the graph (bytes)", lambda: adapter.to_json_bytes(state), 30)
    bench("to_dict of the graph", lambda: adapter.to_dict(state), 30)
    bench("validate+repair+ops_diff of a whole-flow save", lambda: adapter.save(flow, inputs.save_target), 15)
    bench(
        "validate+repair+ops_diff of a whole-flow save that repair fixes",
        lambda: adapter.save(flow, inputs.save_target_to_repair),
        15,
    )
    return results


# --- Memory ------------------------------------------------------------------------------------

MEMORY_STATES = 3


def rss_bytes() -> int:
    return int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1]) * os.sysconf("SC_PAGE_SIZE")


def memory_child(engine: str, flow_path: str) -> dict[str, Any]:
    """In this process: the resident set growth per graph state loaded from JSON text, over a few states.

    Each state holds all of its own values. (From a dict, the Python engine would share the dict's strings with
    its caller, so the growth would not be what the state holds.)
    """
    adapter = ADAPTERS[engine]()
    text = Path(flow_path).read_bytes()

    def build() -> Any:
        return adapter.build_text(text)

    build()  # load the code and warm the allocator
    gc.collect()
    before = rss_bytes()
    states = [build() for _ in range(MEMORY_STATES)]
    gc.collect()
    after = rss_bytes()
    del states
    return {"bytes_per_state": (after - before) // MEMORY_STATES, "states": MEMORY_STATES}


def memory(engine: str, flow_path: Path, script: Path) -> dict[str, Any]:
    output = subprocess.run(  # noqa: S603 - this script, with arguments it chose
        [sys.executable, str(script), "--memory-child", engine, str(flow_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output.strip().splitlines()[-1])


# --- Running -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None, script: Path | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("flow", type=Path, nargs="?")
    parser.add_argument("starter_projects", type=Path, nargs="?")
    parser.add_argument("--engines", default="python,rust")
    parser.add_argument("--scale", type=float, default=1.0, help="multiply the number of runs")
    parser.add_argument("--memory-child", nargs=2, metavar=("ENGINE", "FLOW"))
    args = parser.parse_args(argv)
    if args.memory_child:
        print(json.dumps(memory_child(*args.memory_child)))
        return
    inputs = Inputs(args.flow, args.starter_projects)
    script = script or Path(__file__).resolve()
    for engine in args.engines.split(","):
        adapter = ADAPTERS[engine]()
        scale = args.scale * getattr(adapter, "scale", 1.0)
        for name, result in benchmarks(adapter, inputs, scale).items():
            print(json.dumps({"engine": engine, "benchmark": name, **result}), flush=True)
        result = memory(engine, args.flow, script)
        name = "memory per GraphState loaded from JSON text"
        print(json.dumps({"engine": engine, "benchmark": name, **result}), flush=True)


if __name__ == "__main__":
    main()
