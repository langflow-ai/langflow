"""Build a large flow graph from the nodes and edges of the starter projects.

The engine benchmarks and the differential test need a large real flow. This
script builds one the same way every time: it copies the nodes and edges of
every starter project, in file name order, again and again, until the graph's
JSON text (as ``json.dumps`` writes it with its default separators) reaches
the target size. Each copy gets new node and edge ids, its edges and handles
name the new node ids, and its nodes move so that copies do not overlap.

A stored graph that went through repair has positions on its outputs and tool
actions and ids on its table rows, and the starter projects do not. So each
copy gives every output and tool action a ``__pos__``, and every table row an
``__id__`` and a ``__pos__``, in array order, with ids that depend only on
where the row is. The result breaks no rule, also as a new flow.

    python src/lfx-native/fixtures/tools/large_flow.py STARTER_PROJECTS_DIR OUT.json [--bytes N]

It prints the byte size, the node and edge counts and the SHA-256 of the file
it writes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

TARGET_BYTES = 14_400_000
HANDLE_QUOTE = "œ"
OUTPUTS_PATH = ("data", "node", "outputs")
TABLE_FIELD_TYPES = ({"type": "table"}, {"_input_type": "TableInput"})
COPY_OFFSET = 4000.0


def escape_handle(handle: dict[str, Any]) -> str:
    """A handle's string form: compact JSON with ``œ`` standing for ``"``."""
    return json.dumps(handle, separators=(",", ":"), ensure_ascii=False).replace('"', HANDLE_QUOTE)


def load_projects(folder: Path) -> list[tuple[str, dict[str, Any]]]:
    """The graph of every starter project, in file name order."""
    return [(path.stem, json.loads(path.read_text(encoding="utf-8"))["data"]) for path in sorted(folder.glob("*.json"))]


def _position_items(items: Any) -> None:
    if isinstance(items, list):
        for index, item in enumerate(items):
            if isinstance(item, dict):
                item["__pos__"] = index + 1


def _is_table(field: dict[str, Any]) -> bool:
    return any(all(field.get(key) == value for key, value in condition.items()) for condition in TABLE_FIELD_TYPES)


def normalize_node(node: dict[str, Any], node_id: str) -> None:
    """Give a node's keyed lists positions and its table rows ids, as repair would, without random ids."""
    body = node["data"]["node"]
    _position_items(body.get("outputs"))
    template = body.get("template", {})
    tools = template.get("tools_metadata")
    if isinstance(tools, dict):
        _position_items(tools.get("value"))
    for name, field in template.items():
        if isinstance(field, dict) and _is_table(field) and isinstance(field.get("value"), list):
            rows = field["value"]
            for index, row in enumerate(rows):
                if isinstance(row, dict):
                    row["__id__"] = f"{node_id}-{name}-r{index + 1}"
                    row["__pos__"] = index + 1


def copy_project(graph: dict[str, Any], suffix: str, offset: float) -> tuple[list[Any], list[Any]]:
    """The nodes and edges of one starter project with new ids, moved by ``offset``."""
    nodes = copy.deepcopy(graph["nodes"])
    edges = copy.deepcopy(graph["edges"])
    renamed = {node["id"]: f"{node['id']}-{suffix}" for node in nodes}
    for node in nodes:
        node["id"] = renamed[node["id"]]
        if isinstance(node.get("data"), dict) and "id" in node["data"]:
            node["data"]["id"] = node["id"]
        position = node.get("position")
        if isinstance(position, dict) and isinstance(position.get("x"), (int, float)):
            position["x"] = position["x"] + offset
        normalize_node(node, node["id"])
    for edge in edges:
        edge["id"] = f"{edge['id']}-{suffix}"
        edge["source"] = renamed[edge["source"]]
        edge["target"] = renamed[edge["target"]]
        data = edge.get("data", {})
        for key, end in (("sourceHandle", "source"), ("targetHandle", "target")):
            handle = data.get(key)
            if isinstance(handle, dict):
                handle["id"] = edge[end]
                edge[key] = escape_handle(handle)
    return nodes, edges


def build(folder: Path, target_bytes: int = TARGET_BYTES) -> dict[str, Any]:
    """A flow of starter project copies whose ``json.dumps`` text is at least ``target_bytes`` long."""
    projects = load_projects(folder)
    flow: dict[str, Any] = {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 0.5}}
    # Two characters of separator per item, as ``json.dumps`` writes ", ".
    size = len(json.dumps(flow))
    round_index = 0
    while size < target_bytes:
        for index, (_name, graph) in enumerate(projects):
            suffix = f"c{round_index}p{index}"
            nodes, edges = copy_project(graph, suffix, COPY_OFFSET * round_index)
            flow["nodes"].extend(nodes)
            flow["edges"].extend(edges)
            size += sum(len(json.dumps(item)) + 2 for item in nodes + edges)
            if size >= target_bytes:
                break
        round_index += 1
    return flow


def describe(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    flow = json.loads(data)
    return {
        "path": str(path),
        "bytes": len(data),
        "nodes": len(flow["nodes"]),
        "edges": len(flow["edges"]),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("starter_projects", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--bytes", type=int, default=TARGET_BYTES)
    args = parser.parse_args()
    flow = build(args.starter_projects, args.bytes)
    args.out.write_text(json.dumps(flow), encoding="utf-8")
    print(json.dumps(describe(args.out)))


if __name__ == "__main__":
    main()
