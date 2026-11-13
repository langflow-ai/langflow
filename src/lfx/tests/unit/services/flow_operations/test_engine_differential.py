"""The Python engine and the Rust engine give the same results on random batches of real flows.

A seeded generator writes batches of operations against the starter projects
and a large flow built from them (``src/lfx-native/fixtures/tools/large_flow.py``):
field edits, toggles, new and deleted keys, moves, nodes added, deleted and
pasted, edges added (valid, into a taken input, with broken handles, to a
note, with a repeated id) and deleted, writes to outputs, tool actions and
table rows by key, whole-list writes, odd values (integers of more than 64
bits, numbers too large for a double, non-ASCII text, deep nesting), operations
as JSON text with a number too large for a double, and malformed operations.
Each batch runs on both engine objects in one of six ways: ``apply``,
``stage`` then ``keep``, ``stage`` then ``drop``, ``undo``, ``undo_apply`` or
``replay``. After every batch the test compares whether it was refused, the
whole error (kind, code, message and details), the forward and backward
operations, the graph's JSON text byte for byte, and the graph hash from both
engines. While a batch is staged, both engines' ``to_json`` must give the
committed text and ``to_json(staged=True)`` the same text as ``to_json``
after ``keep``, and ``drop`` must give back the text from before the batch.
``undo`` replays the backward operations of the last batch that applied, as
history playback does; ``undo_apply`` applies them as one new batch, under
every rule, as a user's undo does, and must give back the graph from before
that batch. ``replay`` replays a new batch, with no rule, on a separate pair of
states. A second pair of states replays the log of forward and backward
operations, and must reach the same graph. Every few batches, both engines'
plain graphs validate, repair, compare and diff the graph against the last
one, as it is and with defects added that repair fixes.
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
from lfx.services.flow_operations.json_io import dump_bytes

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
# On the large flow, the plain graphs are compared every this many batches.
LARGE_PLAIN_EVERY = 25

pytestmark = pytest.mark.skipif(not STARTER_PROJECTS.is_dir(), reason="the starter projects are not in this checkout")


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    try:
        import large_flow
    finally:
        sys.path.remove(str(TOOLS))
    return large_flow


# --- Comparing results ----------------------------------------------------------------------------


def _normalized(result: dict[str, Any]) -> dict[str, Any]:
    out = {}
    if "forward_operations" in result:
        out["forward"] = result["forward_operations"]
    if "forward_operations_json" in result:
        # The log's text of each forward operation: what ``to_json`` writes for it, the same bytes from both engines.
        out["forward_json"] = result["forward_operations_json"]
        assert out["forward_json"] == [dump_bytes(operation) for operation in result["forward_operations"]]
    if "backward_operations" in result:
        out["backward"] = result["backward_operations"]
    return out


def _outcome(call: Any) -> tuple[Any, ...]:
    """What a call gave, or its whole error."""
    try:
        return ("ok", call())
    except FlowOperationError as error:
        return ("error", error.kind, error.code, error.details)


def _run(state: Any, mode: str, batch: Any, before: str | None = None) -> tuple[Any, ...]:
    """Run one batch in one way; returns what it gave, or the whole error.

    ``before`` is the graph's JSON text before the batch, when the caller has it. While a staged batch waits,
    ``to_json`` gives the committed text; after ``drop``, the text from before the batch.
    """
    if before is None:
        before = state.to_json()

    def run() -> dict[str, Any]:
        if mode == "apply":
            return _normalized(state.apply(batch, forward=True, backward=True, forward_json=True))
        if mode == "replay":
            return _normalized(state.replay(batch, backward=True))
        result = _normalized(state.stage(batch, forward=True, backward=True, forward_json=True))
        assert state.to_json() == before, "to_json while a batch is staged is not the committed text"
        # The graph with the staged batch: compared between the engines with the result.
        result["staged"] = state.to_json(staged=True)
        if mode == "stage_keep":
            state.keep()
            assert state.to_json() == result["staged"], "keep did not give the staged text"
        else:
            assert state.drop()
            assert state.to_json() == before, "drop did not give back the text from before the batch"
            with pytest.raises(RuntimeError):
                state.to_json(staged=True)
        return result

    outcome = _outcome(run)
    if outcome[0] == "error":
        assert state.to_json() == before, "a refused batch changed the graph"
    return outcome


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
        if roll < 0.04:
            return self.odd_value()
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

    def odd_value(self) -> Any:
        """A value at the edge of what JSON and the engines hold."""
        deep: Any = "leaf"
        for _ in range(self.rng.choice([10, 100, 120])):
            deep = [deep]
        return self.rng.choice(
            [
                2**70,
                -(2**64),
                10**400,
                1e-7,
                -0.0,
                1.5e300,
                5e-324,
                'é œ 😀 \x7f \u2028 \\x41 \\U0001f600 \x00 "',
                {"ключ": "значение", "😀": [1, 2**64 - 1]},
                deep,
            ]
        )

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
        if keys and roll < 0.88:
            # Delete an item and write it again, in two operations of one batch.
            key = self.rng.choice(keys)
            item = copy.deepcopy(next(entry for entry in items if key_of(entry) == key))
            item["note"] = self.value()
            return [
                {"type": "update_nodes", "updates": [self.update(node_id, [*path, {"key": key}], delete=True)]},
                {"type": "update_nodes", "updates": [self.update(node_id, [*path, {"key": key}], item)]},
            ]
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
            return self.field_operations(graph)
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
                return self.field_operations(graph)
            edge = copy.deepcopy(self.rng.choice(edges))
            return [{"type": "delete_edges", "ids": [edge["id"]]}, {"type": "add_edges", "edges": [edge]}]
        return self.malformed(graph)

    def field_operations(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        """Field writes as operations: one ``update_nodes``, or the operations a write needs in a batch."""
        updates = self.field_updates(graph)
        if updates and "type" in updates[0]:
            return updates
        return [{"type": "update_nodes", "updates": updates}]

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

    def not_finite_text(self, graph: dict[str, Any]) -> bytes:
        """A batch as JSON text that sets a value to a number too large for a double: both engines refuse it."""
        node_id = self.rng.choice(graph["nodes"])["id"] if graph["nodes"] else "a"
        update = self.update(node_id, ["position"], {"x": 0})
        return json.dumps([{"type": "update_nodes", "updates": [update]}]).replace('"x": 0', '"x": -1e400').encode()

    def defects(self, graph: dict[str, Any]) -> dict[str, Any]:
        """A copy of ``graph`` with defects that repair fixes the same way every time."""
        broken = copy.deepcopy(graph)
        nodes, edges = broken["nodes"], broken["edges"]
        for _ in range(self.rng.randint(1, 3)):
            roll = self.rng.random()
            if roll < 0.2:
                broken[f"odd_{self.rng.randrange(3)}"] = [1, 10**400]
            elif roll < 0.4 and nodes:
                # A copy of a node with the same id: repair gives the copy a generated id.
                nodes.append(copy.deepcopy(self.rng.choice(nodes)))
            elif roll < 0.55 and nodes:
                self.rng.choice(nodes)["data"] = "not an object"
            elif roll < 0.7 and nodes:
                edges.append({"id": self.fresh("edge"), "source": nodes[0]["id"], "target": "no-such-node"})
            elif roll < 0.85:
                outputs = [node["data"]["node"]["outputs"] for node in nodes if _outputs_of(node)]
                if outputs:
                    output = self.rng.choice(self.rng.choice(outputs))
                    if isinstance(output, dict):
                        output.pop("__pos__", None)
                        output["note"] = self.fresh("note")
            elif edges:
                edge = self.rng.choice(edges)
                if isinstance(edge.get("data"), dict) and "sourceHandle" in edge["data"]:
                    edge.pop("sourceHandle", None)
        return broken


def _outputs_of(node: Any) -> bool:
    data = node.get("data") if isinstance(node, dict) else None
    body = data.get("node") if isinstance(data, dict) else None
    return isinstance(body, dict) and isinstance(body.get("outputs"), list) and bool(body["outputs"])


def batch_of(writer: Writer, graph: dict[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for _ in range(writer.rng.randint(1, 3)):
        operations.extend(writer.operations(graph))
    return operations


MODES = ("apply", "apply", "apply", "stage_keep", "stage_keep", "stage_drop", "undo", "undo_apply", "replay")
# One batch in this many is JSON text with a number too large for a double.
NOT_FINITE_EVERY = 25


def _compare_graphs(python: Any, rust: Any, context: str) -> tuple[dict[str, Any], str]:
    """Both engines' graphs: the same JSON text, byte for byte, and the same hash. Returns the graph and its text."""
    text = python.to_json()
    assert text == rust.to_json(), f"{context}: the engines' JSON text differs"
    assert text.isascii(), context
    data = text.encode()
    # A graph that holds an integer too large for a double has no hash: both engines refuse it alike.
    python_hash = _outcome(lambda: PythonEngine.graph_hash(data))
    rust_hash = _outcome(lambda: RustEngine.graph_hash(data))
    assert python_hash == rust_hash, f"{context}\n python: {python_hash}\n rust:   {rust_hash}"
    return python.to_dict(), text


# Repair gives a new row or edge id at random for these.
_RANDOM_IDS = {"TABLE_ROW_ID_MISSING", "TABLE_ROW_ID_DUPLICATE", "EDGE_ID_MISSING", "EDGE_ID_DUPLICATE"}


def _without_random_ids(text: str, fixes: list[dict[str, Any]]) -> str:
    """A repaired graph's JSON text with each id that repair made at random replaced by the same text."""
    graph = json.loads(text)
    for fix in fixes:
        if fix["code"] in _RANDOM_IDS:
            *parents, last = fix["path"]
            container = graph
            for part in parents:
                container = container[part]
            container[last] = "generated"
    return json.dumps(graph, separators=(",", ":"))


def _compare_plain_graphs(writer: Writer, base: dict[str, Any], graph: dict[str, Any], context: str) -> None:
    """Both engines' plain graphs validate, repair, compare and diff ``graph`` against ``base`` alike."""
    targets = [graph, writer.defects(graph)]
    results = []
    for engine in (PythonEngine, RustEngine):
        found = []
        plain_base = engine.GraphPlain(base)
        for target in targets:
            plain = engine.GraphPlain(target)
            found.append(_outcome(lambda plain=plain: plain.validate(None, check_values=False)))
            found.append(_outcome(lambda plain=plain, base=plain_base: plain.validate(base)))
            repaired = _outcome(lambda plain=plain, base=plain_base: plain.repair(base))
            if repaired[0] == "ok":
                fixed, fixes = repaired[1]
                text = _without_random_ids(fixed.to_json(), fixes)
                found.append(("ok", text, fixes))
                fixed = engine.GraphPlain(text.encode())
                found.append(_outcome(lambda fixed=fixed, base=plain_base: base.ops_diff(fixed)))
                found.append(_outcome(lambda fixed=fixed, base=plain_base: base.equals(fixed)))
            else:
                found.append(repaired)
            found.append(_outcome(lambda plain=plain, base=plain_base: base.ops_diff(plain)))
            found.append(_outcome(lambda plain=plain, base=plain_base: plain.equals(base)))
            found.append(_outcome(plain.graph_hash))
        results.append(found)
    python, rust = results
    for index, (left, right) in enumerate(zip(python, rust, strict=True)):
        assert left == right, f"{context}, plain graph check {index}\n python: {left}\n rust:   {right}"


def drive(flow: dict[str, Any], batches: int, seed: int, *, plain_every: int = 5) -> dict[str, int]:
    """Run ``batches`` random batches on both engines from ``flow``; returns how many of each outcome.

    ``apply``, ``stage_keep`` and ``stage_drop`` run a new batch. ``undo``
    replays the backward operations of the last batch that applied, last
    first, each list in a call of its own, as history playback does.
    ``undo_apply`` applies them, last first, as one new batch. ``replay``
    replays a new batch, with no rule, on a second pair of states that only
    ever replays: replay deletes no edge with its node, so it can leave a
    graph that apply refuses. Every ``plain_every`` batches, the plain graphs
    are compared too.
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
    graph, text_now = _compare_graphs(python, rust, f"seed {seed}, the flow as loaded")
    replay_graph, replay_text = graph, text_now
    plain_base = graph
    last_backward: list[Any] = []
    before_last = graph
    counts = {"applied": 0, "refused": 0, "undone": 0, "undo_applied": 0, "undo_refused": 0, "replayed": 0}

    def same(context: str, python_result: Any, rust_result: Any) -> None:
        assert python_result == rust_result, f"{context}\n python: {python_result}\n rust:   {rust_result}"

    for index in range(batches):
        mode = rng.choice(MODES)
        if mode == "undo":
            context = f"seed {seed}, batch {index}, undo of {json.dumps(last_backward)[:2000]}"
            for operations in reversed(last_backward):
                text = json.dumps(operations)
                python_result = _run(python, "replay", json.loads(text))
                same(context, python_result, _run(rust, "replay", json.loads(text)))
                assert python_result[0] == "ok", f"{context}: {python_result}"
                python_log.replay(json.loads(text))
                rust_log.replay(json.loads(text))
            counts["undone"] += bool(last_backward)
            last_backward = []
            graph, text_now = _compare_graphs(python, rust, context)
        elif mode == "undo_apply":
            batch = [operation for operations in reversed(last_backward) for operation in operations]
            text = json.dumps(batch)
            context = f"seed {seed}, batch {index}, undo as a batch: {text[:2000]}"
            python_result = _run(python, "apply", json.loads(text), text_now)
            same(context, python_result, _run(rust, "apply", json.loads(text), text_now))
            if python_result[0] == "ok" and last_backward:
                counts["undo_applied"] += 1
                python_log.replay(python_result[1]["forward"])
                rust_log.replay(python_result[1]["forward"])
            elif last_backward:
                # An edge the batch removed may break a rule now: a later write may have changed its ends.
                counts["undo_refused"] += 1
            last_backward = []
            graph, text_now = _compare_graphs(python, rust, context)
            if python_result[0] == "ok" and batch:
                # Equal, or both hold an integer too large for a double, which no comparison reads.
                restored = _outcome(lambda graph=graph, base=before_last: PythonEngine.graphs_equal(graph, base))
                assert restored[0] == "error" or restored[1], f"{context}: undo did not give back the graph"
        elif mode == "replay":
            batch = batch_of(writer, replay_graph)
            text = json.dumps(batch)
            context = f"seed {seed}, batch {index}, replay: {text[:2000]}"
            python_result = _run(python_replay, "replay", json.loads(text), replay_text)
            same(context, python_result, _run(rust_replay, "replay", json.loads(text), replay_text))
            counts["replayed"] += python_result[0] == "ok"
            replay_graph, replay_text = _compare_graphs(python_replay, rust_replay, context)
        else:
            if index % NOT_FINITE_EVERY == NOT_FINITE_EVERY - 1:
                data = writer.not_finite_text(graph)
                context = f"seed {seed}, batch {index}, mode {mode}: {data[:2000]!r}"
                python_result = _run(python, mode, data, text_now)
                same(context, python_result, _run(rust, mode, data, text_now))
                assert python_result[0] == "error", context
            else:
                text = json.dumps(batch_of(writer, graph))
                context = f"seed {seed}, batch {index}, mode {mode}: {text[:2000]}"
                python_result = _run(python, mode, json.loads(text), text_now)
                same(context, python_result, _run(rust, mode, json.loads(text), text_now))
            if python_result[0] == "ok":
                counts["applied"] += 1
                if mode in ("apply", "stage_keep"):
                    python_log.replay(python_result[1]["forward"])
                    rust_log.replay(python_result[1]["forward"])
                    last_backward = python_result[1]["backward"]
                    before_last = graph
            else:
                counts["refused"] += 1
            graph, text_now = _compare_graphs(python, rust, context)
            log_text = python_log.to_json()
            assert log_text == rust_log.to_json(), f"{context}: the log replays differ"
            assert log_text == text_now, f"{context}: the log replay differs from the graph"
        if index % plain_every == 0:
            _compare_plain_graphs(writer, plain_base, graph, f"seed {seed}, batch {index}")
            plain_base = graph
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
    assert counts["undo_applied"] > 0
    assert counts["replayed"] > 0


def test_both_engines_agree_on_random_batches_of_the_large_flow():
    flow = _tools().build(STARTER_PROJECTS)
    counts = drive(flow, BATCHES_ON_THE_LARGE_FLOW, SEED - 1, plain_every=LARGE_PLAIN_EVERY)
    assert counts["applied"] > 0
    assert counts["refused"] > 0
    assert counts["undo_applied"] > 0
