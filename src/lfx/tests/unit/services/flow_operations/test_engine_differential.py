"""The Python engine and the Rust engine give the same results on random batches of real flows.

A seeded generator writes batches of operations against the starter projects
and a large flow built from them (``src/lfx-native/fixtures/tools/large_flow.py``):
field edits, toggles, new and deleted keys, moves, nodes added, deleted and
pasted, edges added (valid, into a taken input, with broken handles, to a
note, with a repeated id) and deleted, writes to outputs, tool actions and
table rows by key, whole-list writes, and malformed operations. Each batch
runs on both engine objects in one of five ways: ``apply``, ``stage`` then
``keep``, ``stage`` then ``drop``, ``undo`` or ``replay``. After every batch the test
compares whether it was refused, the error kind and code, the forward and
backward operations, the graph hash, and canonical equality of the graphs.
``undo`` replays the backward operations of the last batch that applied, as
history playback does, and ``replay`` replays a new batch, with no rule, on a
separate pair of states. A second pair of states replays the log of forward
and backward operations, and must reach the same graph.

The ids inside a ``delete_nodes`` or ``delete_edges`` and the entries of an
``add_nodes`` or ``add_edges`` are compared in id order: their order is not
state, and the two engines keep sets of edge ids in different orders.
"""

from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path
from typing import Any

import pytest
from lfx.services.flow_operations.engine import PythonEngine, RustEngine
from lfx.services.flow_operations.exceptions import FlowOperationError

lfx_native = pytest.importorskip("lfx_native")

REPO = Path(__file__).resolve().parents[5]
STARTER_PROJECTS = REPO / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"
TOOLS = REPO / "lfx-native" / "fixtures" / "tools"
SEED = 20261101
SMALL_FLOWS = (
    "Basic Prompting",
    "Blog Writer",
    "Document Q&A",
    "Hybrid Search RAG",
    "Memory Chatbot",
    "Price Deal Finder",
    "Research Translation Loop",
    "Simple Agent",
    "Vector Store RAG",
)
BATCHES_PER_SMALL_FLOW = 300
BATCHES_ON_THE_LARGE_FLOW = 300
# On the large flow, the Python engine hashes the graph every this many batches; the Rust engine hashes it every batch.
LARGE_PYTHON_HASH_EVERY = 25

pytestmark = pytest.mark.skipif(not STARTER_PROJECTS.is_dir(), reason="the starter projects are not in this checkout")


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    try:
        import large_flow
    finally:
        sys.path.remove(str(TOOLS))
    return large_flow


# --- Comparing results ----------------------------------------------------------------------------

_ORDERLESS = {"delete_nodes": "ids", "delete_edges": "ids", "add_nodes": "nodes", "add_edges": "edges"}


def _normalized_operations(operations: list[Any]) -> list[Any]:
    out = []
    for operation in operations:
        key = _ORDERLESS.get(operation.get("type"))
        if key:
            items = sorted(operation[key], key=lambda item: item if isinstance(item, str) else item["id"])
            out.append({**operation, key: items})
        else:
            out.append(operation)
    return out


def _normalized(result: dict[str, Any]) -> dict[str, Any]:
    out = {}
    if "forward_operations" in result:
        out["forward"] = _normalized_operations(result["forward_operations"])
    if "backward_operations" in result:
        out["backward"] = [_normalized_operations(operations) for operations in result["backward_operations"]]
    return out


def _run(state: Any, mode: str, batch: list[Any]) -> tuple[Any, ...]:
    """Run one batch in one way; returns what it gave, or the error kind and code."""
    try:
        if mode == "apply":
            return ("ok", _normalized(state.apply(batch, forward=True, backward=True)))
        if mode == "stage_keep":
            result = state.stage(batch, forward=True, backward=True)
            state.keep()
            return ("ok", _normalized(result))
        if mode == "stage_drop":
            result = state.stage(batch, forward=True, backward=True)
            assert state.drop()
            return ("ok", _normalized(result))
        return ("ok", _normalized(state.replay(batch, backward=True)))
    except FlowOperationError as error:
        return ("error", error.kind, error.code)


# --- Writing random batches ---------------------------------------------------------------------------

TEMPLATE = ("data", "node", "template")
OUTPUTS = ("data", "node", "outputs")


class Writer:
    """Random operations against the graph as it stands, from a seeded generator."""

    def __init__(self, rng: random.Random, pool: list[dict[str, Any]], large_flow: Any) -> None:
        self.rng = rng
        self.pool = pool
        self.large_flow = large_flow
        self.counter = 0
        self.removed_edges: list[dict[str, Any]] = []

    def fresh(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-r{self.counter}"

    def value(self) -> Any:
        roll = self.rng.random()
        if roll < 0.3:
            return f"text {self.rng.randrange(1000)}"
        if roll < 0.45:
            return self.rng.randrange(-5, 50)
        if roll < 0.6:
            return round(self.rng.uniform(-10, 10), 3)
        if roll < 0.7:
            return self.rng.random() < 0.5
        if roll < 0.75:
            return None
        if roll < 0.85:
            return [self.rng.randrange(10), "x"]
        return {"nested": {"k": self.value() if self.rng.random() < 0.3 else 1}}

    def update(self, node_id: str, path: list[Any], value: Any = None, *, delete: bool = False) -> dict[str, Any]:
        if delete:
            return {"id": node_id, "op": "delete_field", "path": path}
        return {"id": node_id, "op": "set_field", "path": path, "value": value}

    def field_updates(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        node = self.rng.choice(graph["nodes"])
        node_id = node["id"]
        template = node["data"]["node"]["template"]
        fields = [name for name, field in template.items() if isinstance(field, dict)]
        roll = self.rng.random()
        if not fields or roll < 0.08:
            return [self.update(node_id, ["position"], {"x": self.rng.randrange(1000), "y": self.rng.randrange(500)})]
        name = self.rng.choice(fields)
        field = template[name]
        base = [*TEMPLATE, name]
        if roll < 0.45:
            return [self.update(node_id, [*base, "value"], self.value())]
        if roll < 0.55:
            return [
                self.update(
                    node_id, [*base, self.rng.choice(["advanced", "show", "tool_mode"])], self.rng.random() < 0.5
                )
            ]
        if roll < 0.62:
            return [self.update(node_id, [*base, f"extra_{self.rng.randrange(3)}"], self.value())]
        if roll < 0.7:
            key = self.rng.choice([*field.keys(), "missing_key"])
            return [self.update(node_id, [*base, key], delete=True)]
        if roll < 0.75:
            # Removes the field, and the edges into it.
            return [self.update(node_id, base, delete=True)]
        if roll < 0.8:
            return [self.update(node_id, [*TEMPLATE, "no_such_field", "value"], 1)]
        if roll < 0.85:
            return [self.update(node_id, [*base, "value"], self.value()), self.update(node_id, ["position"], {"x": 1})]
        if roll < 0.93:
            return self.keyed_updates(node)
        return [self.update(node_id, [*TEMPLATE, name], {"type": "str", "value": self.value()})]

    def keyed_updates(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        """Writes by key into the node's outputs, tool actions or a table."""
        node_id = node["id"]
        body = node["data"]["node"]
        lists: list[tuple[list[Any], Any, str]] = []
        if isinstance(body.get("outputs"), list):
            lists.append(([*OUTPUTS], body["outputs"], "name"))
        for name, field in body["template"].items():
            if not isinstance(field, dict) or not isinstance(field.get("value"), list):
                continue
            if field.get("type") == "table" or field.get("_input_type") == "TableInput":
                lists.append(([*TEMPLATE, name, "value"], field["value"], "__id__"))
            elif name == "tools_metadata":
                lists.append(([*TEMPLATE, name, "value"], field["value"], "tags"))
        if not lists:
            return [self.update(node_id, [*OUTPUTS, {"key": "out"}, "hidden"], value=True)]
        path, items, key_name = self.rng.choice(lists)

        def key_of(item: Any) -> Any:
            if not isinstance(item, dict):
                return None
            if key_name == "tags":
                tags = item.get("tags")
                return tags[0] if isinstance(tags, list) and tags else None
            return item.get(key_name)

        keys = [key for key in (key_of(item) for item in items) if isinstance(key, str) and key]
        roll = self.rng.random()
        if keys and roll < 0.3:
            key = self.rng.choice(keys)
            return [self.update(node_id, [*path, {"key": key}, "__pos__"], round(self.rng.uniform(0, 20), 2))]
        if keys and roll < 0.45:
            key = self.rng.choice(keys)
            return [self.update(node_id, [*path, {"key": key}, "note"], self.value())]
        if roll < 0.65:
            new_key = self.fresh("item")
            item: dict[str, Any] = {key_name: [new_key] if key_name == "tags" else new_key}
            if key_name == "name":
                item["types"] = ["Message"]
            if self.rng.random() < 0.8:
                item["__pos__"] = round(self.rng.uniform(0, 20), 2)
            return [self.update(node_id, [*path, {"key": new_key}], item)]
        if keys and roll < 0.8:
            key = self.rng.choice(keys)
            return [self.update(node_id, [*path, {"key": key}], delete=True)]
        if keys and roll < 0.85:
            # A write that changes an item's key: refused by the parser.
            key = self.rng.choice(keys)
            return [self.update(node_id, [*path, {"key": key}, key_name], "renamed")]
        if roll < 0.92:
            # The whole list, with positions and keys.
            whole = copy.deepcopy(items)
            for index, entry in enumerate(whole):
                if isinstance(entry, dict):
                    entry["__pos__"] = index + 1
                    if key_name == "__id__":
                        entry.setdefault("__id__", self.fresh("row"))
            return [self.update(node_id, path, whole)]
        return [self.update(node_id, [*path, {"key": "missing"}, "x"], 1)]

    def edge_between(self, graph: dict[str, Any], edge_id: str | None = None) -> dict[str, Any]:
        """An edge from a random output to a random field: often valid, often into a taken input."""
        sources = [node for node in graph["nodes"] if node["data"]["node"].get("outputs")]
        if not sources:
            sources = graph["nodes"]
        source = self.rng.choice(sources)
        target = self.rng.choice(graph["nodes"])
        outputs = source["data"]["node"].get("outputs") or [{"name": "out"}]
        output = self.rng.choice(outputs)
        name = output.get("name") if isinstance(output, dict) else "out"
        fields = [key for key, field in target["data"]["node"]["template"].items() if isinstance(field, dict)] or ["x"]
        field = self.rng.choice(fields)
        source_handle = {"dataType": "X", "id": source["id"], "name": name, "output_types": ["Message"]}
        target_handle = {"fieldName": field, "id": target["id"], "inputTypes": ["Message"], "type": "str"}
        escape = self.large_flow.escape_handle
        return {
            "id": edge_id or self.fresh("edge"),
            "source": source["id"],
            "target": target["id"],
            "sourceHandle": escape(source_handle),
            "targetHandle": escape(target_handle),
            "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
        }

    def operations(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        roll = self.rng.random()
        nodes, edges = graph["nodes"], graph["edges"]
        if roll < 0.45 or not nodes:
            if not nodes:
                return [{"type": "add_nodes", "nodes": [self.pooled_node()]}]
            return [{"type": "update_nodes", "updates": self.field_updates(graph)}]
        if roll < 0.52:
            node = self.pooled_node()
            if self.rng.random() < 0.15:
                node["id"] = self.rng.choice(nodes)["id"]
            return [{"type": "add_nodes", "nodes": [node]}]
        if roll < 0.6:
            ids = [node["id"] for node in self.rng.sample(nodes, min(len(nodes), self.rng.randint(1, 2)))]
            if self.rng.random() < 0.15:
                ids.append("no-such-node")
            return [{"type": "delete_nodes", "ids": ids}]
        if roll < 0.72:
            choice = self.rng.random()
            if self.removed_edges and choice < 0.35:
                edge = self.removed_edges.pop(self.rng.randrange(len(self.removed_edges)))
            elif edges and choice < 0.45:
                # A repeated id.
                edge = self.edge_between(graph, self.rng.choice(edges)["id"])
            elif choice < 0.55:
                edge = self.edge_between(graph)
                edge["sourceHandle"] = "not a handle"
            else:
                edge = self.edge_between(graph)
            return [{"type": "add_edges", "edges": [edge]}]
        if roll < 0.82:
            if not edges:
                return [{"type": "delete_edges", "ids": ["no-such-edge"]}]
            chosen = self.rng.sample(edges, min(len(edges), self.rng.randint(1, 2)))
            self.removed_edges.extend(copy.deepcopy(chosen))
            ids = [edge["id"] for edge in chosen]
            if self.rng.random() < 0.2:
                ids.append("no-such-edge")
            return [{"type": "delete_edges", "ids": ids}]
        if roll < 0.88:
            return self.paste()
        if roll < 0.94:
            # Delete an edge and add it back: a rewire.
            if not edges:
                return [{"type": "update_nodes", "updates": self.field_updates(graph)}]
            edge = copy.deepcopy(self.rng.choice(edges))
            return [{"type": "delete_edges", "ids": [edge["id"]]}, {"type": "add_edges", "edges": [edge]}]
        return self.malformed(graph)

    def pooled_node(self) -> dict[str, Any]:
        node = copy.deepcopy(self.rng.choice(self.pool))
        node["id"] = self.fresh(node["id"].split("-")[0])
        return node

    def paste(self) -> list[dict[str, Any]]:
        projects = self.large_flow_projects
        _name, graph = self.rng.choice(projects)
        nodes, edges = self.large_flow.copy_project(graph, self.fresh("paste"), 50_000.0)
        return [{"type": "add_nodes", "nodes": nodes}, {"type": "add_edges", "edges": edges}]

    def malformed(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        node_id = self.rng.choice(graph["nodes"])["id"]
        return self.rng.choice(
            [
                [{"type": "update_nodes", "updates": [self.update(node_id, ["data", "node"], {})]}],
                [{"type": "update_nodes", "updates": [self.update(node_id, ["data", 0], 1)]}],
                [{"type": "update_metadata", "fields": {}}],
                [{"type": "delete_nodes", "ids": [node_id], "extra": 1}],
                [{"type": "add_edges", "edges": [{"id": "e", "source": node_id}]}],
                [
                    {
                        "type": "update_nodes",
                        "updates": [self.update(node_id, ["position"], 1), self.update(node_id, ["position"], 2)],
                    }
                ],
            ]
        )


def batch_of(writer: Writer, graph: dict[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for _ in range(writer.rng.randint(1, 3)):
        operations.extend(writer.operations(graph))
    return operations


MODES = ("apply", "apply", "apply", "stage_keep", "stage_keep", "stage_drop", "undo", "replay")


def _compare_graphs(python: Any, rust: Any, context: str, *, python_hash: bool) -> dict[str, Any]:
    """Both engines' graphs: the same hash and canonically equal. Returns the Python engine's graph."""
    graph = python.to_dict()
    rust_graph = rust.to_dict()
    rust_hash = RustEngine.graph_hash(rust_graph)
    assert RustEngine.graph_hash(graph) == rust_hash, context
    assert RustEngine.graphs_equal(graph, rust_graph), context
    if python_hash:
        assert PythonEngine.graph_hash(graph) == rust_hash, context
        assert PythonEngine.graphs_equal(graph, rust_graph), context
    return graph


def drive(flow: dict[str, Any], batches: int, seed: int, *, python_hash_every: int = 1) -> dict[str, int]:
    """Run ``batches`` random batches on both engines from ``flow``; returns how many of each outcome.

    ``apply``, ``stage_keep`` and ``stage_drop`` run a new batch. ``undo``
    replays the backward operations of the last batch that applied, last
    first, each list in a call of its own, as history playback does.
    ``replay`` replays a new batch, with no rule, on a second pair of states
    that only ever replays: replay deletes no edge with its node, so it can
    leave a graph that apply refuses.
    """
    large_flow = _tools()
    rng = random.Random(seed)  # noqa: S311 - a reproducible test, not secrets
    projects = large_flow.load_projects(STARTER_PROJECTS)
    pool = [node for _, graph in projects for node in graph["nodes"]]
    writer = Writer(rng, pool, large_flow)
    writer.large_flow_projects = [(name, graph) for name, graph in projects if len(graph["nodes"]) <= 6]
    python, rust = PythonEngine.GraphState(flow), RustEngine.GraphState(flow)
    python_log, rust_log = PythonEngine.GraphState(flow), RustEngine.GraphState(flow)
    python_replay, rust_replay = PythonEngine.GraphState(flow), RustEngine.GraphState(flow)
    graph = python.to_dict()
    replay_graph = graph
    last_backward: list[Any] = []
    counts = {"applied": 0, "refused": 0, "undone": 0, "replayed": 0}
    for index in range(batches):
        mode = rng.choice(MODES)
        python_hash = index % python_hash_every == 0 or index == batches - 1
        if mode == "undo":
            context = f"seed {seed}, batch {index}, undo of {json.dumps(last_backward)[:2000]}"
            for operations in reversed(last_backward):
                text = json.dumps(operations)
                python_result = _run(python, "replay", json.loads(text))
                rust_result = _run(rust, "replay", json.loads(text))
                assert python_result == rust_result, f"{context}\n python: {python_result}\n rust:   {rust_result}"
                assert python_result[0] == "ok", f"{context}: {python_result}"
                python_log.replay(json.loads(text))
                rust_log.replay(json.loads(text))
            counts["undone"] += bool(last_backward)
            last_backward = []
            graph = _compare_graphs(python, rust, context, python_hash=python_hash)
            continue
        if mode == "replay":
            batch = batch_of(writer, replay_graph)
            text = json.dumps(batch)
            context = f"seed {seed}, batch {index}, replay: {text[:2000]}"
            python_result = _run(python_replay, "replay", json.loads(text))
            rust_result = _run(rust_replay, "replay", json.loads(text))
            assert python_result == rust_result, f"{context}\n python: {python_result}\n rust:   {rust_result}"
            counts["replayed"] += python_result[0] == "ok"
            replay_graph = _compare_graphs(python_replay, rust_replay, context, python_hash=python_hash)
            continue
        batch = batch_of(writer, graph)
        text = json.dumps(batch)
        python_result = _run(python, mode, json.loads(text))
        rust_result = _run(rust, mode, json.loads(text))
        context = f"seed {seed}, batch {index}, mode {mode}: {text[:2000]}"
        assert python_result == rust_result, f"{context}\n python: {python_result}\n rust:   {rust_result}"
        if python_result[0] == "ok":
            counts["applied"] += 1
            if mode in ("apply", "stage_keep"):
                python_log.replay(python_result[1]["forward"])
                rust_log.replay(python_result[1]["forward"])
                last_backward = python_result[1]["backward"]
        else:
            counts["refused"] += 1
        graph = _compare_graphs(python, rust, context, python_hash=python_hash)
        if python_hash:
            assert PythonEngine.graphs_equal(python_log.to_dict(), graph), f"{context}: the Python log replay differs"
            assert RustEngine.graphs_equal(rust_log.to_dict(), graph), f"{context}: the Rust log replay differs"
    return counts


def _normalized_flow(name: str) -> dict[str, Any]:
    """A starter project as repair would leave it: outputs and tool actions with positions, rows with ids."""
    large_flow = _tools()
    graph = json.loads((STARTER_PROJECTS / f"{name}.json").read_text(encoding="utf-8"))["data"]
    nodes, edges = large_flow.copy_project(graph, "n", 0.0)
    return {"nodes": nodes, "edges": edges}


FLOWS = [pytest.param(name, False, id=f"{name}-as-stored") for name in SMALL_FLOWS] + [
    pytest.param(name, True, id=f"{name}-with-positions") for name in SMALL_FLOWS
]


@pytest.mark.parametrize(("name", "with_positions"), FLOWS)
def test_both_engines_agree_on_random_batches_of_a_starter_project(name, with_positions):
    if with_positions:
        flow = _normalized_flow(name)
    else:
        flow = json.loads((STARTER_PROJECTS / f"{name}.json").read_text(encoding="utf-8"))["data"]
    seed = SEED + SMALL_FLOWS.index(name) * 2 + int(with_positions)
    counts = drive(flow, BATCHES_PER_SMALL_FLOW // 2, seed)
    assert counts["applied"] > 0
    assert counts["refused"] > 0
    assert counts["undone"] > 0
    assert counts["replayed"] > 0


def test_both_engines_agree_on_random_batches_of_the_large_flow():
    flow = _tools().build(STARTER_PROJECTS)
    counts = drive(flow, BATCHES_ON_THE_LARGE_FLOW, SEED - 1, python_hash_every=LARGE_PYTHON_HASH_EVERY)
    assert counts["applied"] > 0
    assert counts["refused"] > 0
