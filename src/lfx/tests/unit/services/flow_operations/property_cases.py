"""Generate the cross-language property fixture: random valid transactions over a small graph.

Every engine that applies flow operations must replay these transactions to
the same graph. The Python engine generated them, so ``test_property_cases``
checks that it still agrees; the editor's applier runs the same file and
compares the hashes.

Regenerate after a deliberate change to apply semantics, from ``src/lfx``:

    uv run python tests/unit/services/flow_operations/property_cases.py

The base is a small synthetic graph with a table, a legacy table, keyed
lists, a single-input and a list field, and a note. Starter projects are
covered by tests that load them at test time instead.
"""

from __future__ import annotations

import copy
import random
import string
import sys
from pathlib import Path
from typing import Any

from lfx.services.flow_operations import (
    FlowOperationError,
    apply_flow_operations,
    graph_hash,
    json_type,
    load_node_schema,
    parse_flow_operations,
)
from lfx.services.flow_operations.fractional_index import generate_key_between, generate_n_keys_between

sys.path.insert(0, str(Path(__file__).parent))
from fixture_json import dumps

FIXTURE = Path(__file__).parent / "fixtures" / "property_cases.json"
SEED = 20261003
SEQUENCES = 30
TRANSACTIONS_PER_SEQUENCE = 6
TEMPLATE = ("data", "node", "template")
OUTPUTS = ("data", "node", "outputs")


def _edge(edge_id: str, source: str, output: str, target: str, field: str) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "data": {"sourceHandle": {"name": output}, "targetHandle": {"fieldName": field, "inputTypes": ["Message"]}},
    }


def base_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "src",
                "data": {
                    "node": {
                        "template": {"text": {"type": "str", "value": "hi"}},
                        "outputs": [{"name": "out"}, {"name": "alt", "hidden": None}],
                    }
                },
            },
            {
                "id": "dst",
                "data": {
                    "node": {
                        "template": {
                            "one": {"type": "str", "value": ""},
                            "many": {"type": "str", "list": True, "value": ""},
                            "num": {"type": "int", "value": 1},
                            "flag": {"type": "bool", "value": False, "advanced": False},
                            "rows": {
                                "type": "table",
                                "value": [{"_id": "r1", "_pos": "a0", "v": "x"}, {"_id": "r2", "_pos": "a1", "v": "y"}],
                            },
                            "legacy": {"type": "table", "value": [{"v": "1"}, {"v": "2"}]},
                            "tools_metadata": {
                                "type": "tools",
                                "value": [{"tags": ["search"], "status": True}, {"tags": ["fetch"], "status": False}],
                            },
                        },
                        "outputs": [{"name": "res"}],
                    }
                },
            },
            {"id": "note", "type": "noteNode", "data": {"node": {"template": {}}}},
        ],
        "edges": [_edge("e1", "src", "out", "dst", "one"), _edge("e2", "src", "alt", "dst", "many")],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


class Generator:
    """Proposes random transactions; each one is kept only if the engine accepts it."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.counter = 0
        self.removed_edges: list[dict[str, Any]] = []

    def next_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-p{self.counter}"

    def text(self) -> str:
        return "".join(self.rng.choice(string.ascii_letters + " ") for _ in range(self.rng.randint(1, 12)))

    def set_entry(self, node_id: str, path: tuple, value: Any, current: Any = None, *, exists: bool) -> dict:
        entry = {"id": node_id, "op": "set_field", "path": list(path), "value": value}
        if exists and json_type(current) != json_type(value):
            entry["from_type"] = json_type(current)
        if self.rng.random() < 0.3:
            entry["expect"] = {"value": current} if exists else {"absent": True}
        return entry

    def propose(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        moves = [
            self.edit_value,
            self.edit_value,
            self.toggle_advanced,
            self.move_node,
            self.edit_table,
            self.edit_table,
            self.toggle_output,
            self.toggle_tool,
            self.remove_edge,
            self.restore_edge,
            self.connect,
            self.update_edge,
            self.remove_field,
            self.remove_output,
            self.copy_node,
            self.remove_node,
            self.edit_metadata,
        ]
        return self.rng.choice(moves)(graph)

    def components(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        return [node for node in graph["nodes"] if node.get("type") != "noteNode"] or graph["nodes"]

    def fields(self, node: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        template = node["data"]["node"]["template"]
        return [(name, field) for name, field in template.items() if isinstance(field, dict) and name != "code"]

    def edit_value(self, graph):
        node = self.rng.choice(self.components(graph))
        candidates = [(n, f) for n, f in self.fields(node) if isinstance(f.get("value"), (str, bool))]
        if not candidates:
            return []
        name, field = self.rng.choice(candidates)
        current = field["value"]
        value = (not current) if isinstance(current, bool) else self.text()
        path = (*TEMPLATE, name, "value")
        return [{"type": "update_nodes", "updates": [self.set_entry(node["id"], path, value, current, exists=True)]}]

    def toggle_advanced(self, graph):
        node = self.rng.choice(self.components(graph))
        candidates = self.fields(node)
        if not candidates:
            return []
        name, field = self.rng.choice(candidates)
        current = field.get("advanced")
        path = (*TEMPLATE, name, "advanced")
        entry = self.set_entry(node["id"], path, not current, current, exists="advanced" in field)
        return [{"type": "update_nodes", "updates": [entry]}]

    def move_node(self, graph):
        node = self.rng.choice(graph["nodes"])
        position = {"x": self.rng.randint(-500, 1500), "y": self.rng.randint(-500, 1500)}
        return [
            {
                "type": "update_nodes",
                "updates": [
                    self.set_entry(node["id"], ("position",), position, node.get("position"), exists="position" in node)
                ],
            }
        ]

    def edit_table(self, graph):
        schema = load_node_schema()
        tables = [
            (node, name, field)
            for node in self.components(graph)
            for name, field in self.fields(node)
            if schema.keyed_list_at(node, (*TEMPLATE, name, "value")) is not None
            and schema.keyed_list_at(node, (*TEMPLATE, name, "value")).kind == "table"
            and isinstance(field.get("value"), list)
        ]
        if not tables:
            return []
        node, name, field = self.rng.choice(tables)
        rows = field["value"]
        path = (*TEMPLATE, name, "value")
        if not rows or not all(isinstance(row, dict) and row.get("_id") for row in rows):
            # The first edit of a legacy table writes it whole, with ids and positions.
            positions = generate_n_keys_between(None, None, len(rows))
            keyed = [
                {**row, "_id": self.next_id("row"), "_pos": position}
                for row, position in zip(rows, positions, strict=True)
            ]
            if not keyed:
                keyed = [{"_id": self.next_id("row"), "_pos": "a0", "name": self.text()}]
            entry = {"id": node["id"], "op": "set_field", "path": list(path), "value": keyed, "expect": {"value": rows}}
            return [{"type": "update_nodes", "updates": [entry]}]
        action = self.rng.choice(["cell", "add", "delete", "move"])
        row = self.rng.choice(rows)
        selector = {"id": row["_id"]}
        if action == "cell":
            column = self.rng.choice(sorted(key for key in row if key not in {"_id", "_pos"}) or ["name"])
            entry = self.set_entry(
                node["id"], (*path, selector, column), self.text(), row.get(column), exists=column in row
            )
        elif action == "add":
            index = rows.index(row)
            after = rows[index + 1]["_pos"] if index + 1 < len(rows) else None
            new_id = self.next_id("row")
            new_row = {"_id": new_id, "_pos": generate_key_between(row["_pos"], after), "name": self.text()}
            entry = {"id": node["id"], "op": "set_field", "path": [*path, {"id": new_id}], "value": new_row}
        elif action == "delete":
            entry = {"id": node["id"], "op": "delete_field", "path": [*path, selector]}
        else:
            positions = sorted(other["_pos"] for other in rows)
            entry = self.set_entry(
                node["id"],
                (*path, selector, "_pos"),
                generate_key_between(None, positions[0])
                if self.rng.random() < 0.5
                else generate_key_between(positions[-1], None),
                row["_pos"],
                exists=True,
            )
        return [{"type": "update_nodes", "updates": [entry]}]

    def toggle_output(self, graph):
        candidates = [
            (node, output)
            for node in self.components(graph)
            for output in node["data"]["node"].get("outputs", [])
            if isinstance(output, dict) and output.get("name")
        ]
        if not candidates:
            return []
        node, output = self.rng.choice(candidates)
        current = output.get("hidden")
        path = (*OUTPUTS, {"key": output["name"]}, "hidden")
        return [
            {
                "type": "update_nodes",
                "updates": [self.set_entry(node["id"], path, not current, current, exists="hidden" in output)],
            }
        ]

    def toggle_tool(self, graph):
        candidates = [
            (node, tool)
            for node in self.components(graph)
            for tool in (node["data"]["node"]["template"].get("tools_metadata") or {}).get("value") or []
            if isinstance(tool, dict) and isinstance(tool.get("tags"), list) and tool["tags"]
        ]
        if not candidates:
            return []
        node, tool = self.rng.choice(candidates)
        current = tool.get("status")
        path = (*TEMPLATE, "tools_metadata", "value", {"key": tool["tags"][0]}, "status")
        return [
            {
                "type": "update_nodes",
                "updates": [self.set_entry(node["id"], path, not current, current, exists="status" in tool)],
            }
        ]

    def remove_edge(self, graph):
        if not graph["edges"]:
            return []
        edge = self.rng.choice(graph["edges"])
        self.removed_edges.append(edge)
        return [{"type": "delete_edges", "ids": [edge["id"]]}]

    def restore_edge(self, _graph):
        if not self.removed_edges:
            return []
        edge = self.removed_edges.pop(self.rng.randrange(len(self.removed_edges)))
        return [{"type": "add_edges", "edges": [{**copy.deepcopy(edge), "id": self.next_id("e")}]}]

    def connect(self, graph):
        sources = [node["id"] for node in graph["nodes"] if node["data"]["node"].get("outputs")]
        targets = [node["id"] for node in graph["nodes"] if "many" in node["data"]["node"]["template"]]
        if not sources or not targets:
            return []
        source = self.rng.choice(sources)
        output = self.rng.choice(
            next(node for node in graph["nodes"] if node["id"] == source)["data"]["node"]["outputs"]
        )
        return [
            {
                "type": "add_edges",
                "edges": [_edge(self.next_id("e"), source, output["name"], self.rng.choice(targets), "many")],
            }
        ]

    def update_edge(self, graph):
        edges = [edge for edge in graph["edges"] if isinstance((edge.get("data") or {}).get("targetHandle"), dict)]
        if not edges:
            return []
        edge = self.rng.choice(edges)
        current = edge["data"]["targetHandle"].get("inputTypes")
        value = sorted({*(current or []), self.rng.choice(["Message", "Data", "Text", "DataFrame"])})
        entry = self.set_entry(
            edge["id"],
            ("data", "targetHandle", "inputTypes"),
            value,
            current,
            exists="inputTypes" in edge["data"]["targetHandle"],
        )
        return [{"type": "update_edges", "updates": [entry]}]

    def remove_field(self, graph):
        node = self.rng.choice(self.components(graph))
        candidates = self.fields(node)
        if not candidates:
            return []
        name, _ = self.rng.choice(candidates)
        return [
            {"type": "update_nodes", "updates": [{"id": node["id"], "op": "delete_field", "path": [*TEMPLATE, name]}]}
        ]

    def remove_output(self, graph):
        candidates = [
            (node, output)
            for node in self.components(graph)
            for output in node["data"]["node"].get("outputs", [])
            if isinstance(output, dict) and output.get("name")
        ]
        if not candidates:
            return []
        node, output = self.rng.choice(candidates)
        return [
            {
                "type": "update_nodes",
                "updates": [{"id": node["id"], "op": "delete_field", "path": [*OUTPUTS, {"key": output["name"]}]}],
            }
        ]

    def copy_node(self, graph):
        node = copy.deepcopy(self.rng.choice(graph["nodes"]))
        node["id"] = self.next_id(node["data"].get("type") or "node")
        node["data"]["id"] = node["id"]
        node["position"] = {"x": self.rng.randint(0, 900), "y": self.rng.randint(0, 900)}
        return [{"type": "add_nodes", "nodes": [node]}]

    def remove_node(self, graph):
        if len(graph["nodes"]) <= 2:
            return []
        return [{"type": "delete_nodes", "ids": [self.rng.choice(graph["nodes"])["id"]]}]

    def edit_metadata(self, _graph):
        return [{"type": "update_metadata", "fields": {"description": self.text()}, "delete_keys": []}]


def generate() -> dict[str, Any]:
    rng = random.Random(SEED)  # noqa: S311 - a reproducible fixture, not a secret
    base = base_graph()
    sequences = []
    for index in range(SEQUENCES):
        generator = Generator(rng)
        graph = base
        transactions: list[list[dict[str, Any]]] = []
        attempts = 0
        while len(transactions) < TRANSACTIONS_PER_SEQUENCE and attempts < TRANSACTIONS_PER_SEQUENCE * 30:
            attempts += 1
            transaction = generator.propose(graph)
            if not transaction:
                continue
            try:
                graph = apply_flow_operations(graph, parse_flow_operations(copy.deepcopy(transaction))).flow_data
            except FlowOperationError:
                continue
            transactions.append(transaction)
        sequences.append(
            {"name": f"sequence {index + 1}", "transactions": transactions, "graph_hash": graph_hash(graph)}
        )
    return {
        "description": (
            "Cross-language property fixture, generated by property_cases.py. For each sequence, apply each "
            "transaction in order to `base`, one apply call per transaction; every one is accepted. `graph_hash` is "
            "the SHA-256 of the final graph's canonical form (view state removed, handles canonical, nodes and edges "
            "ordered by id, RFC 8785)."
        ),
        "seed": SEED,
        "base": base,
        "sequences": sequences,
    }


def main() -> None:
    FIXTURE.write_text(dumps(generate()), encoding="utf-8")


if __name__ == "__main__":
    main()
