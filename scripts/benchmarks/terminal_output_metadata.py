"""Measure only per-vertex output metadata; graph setup/execution is not timed.

Run with the backend and lfx source directories on PYTHONPATH:
uv run python scripts/benchmarks/terminal_output_metadata.py
"""

import json
from statistics import median
from time import perf_counter
from types import SimpleNamespace

import langflow.api.v1  # noqa: F401 - initialize route schemas before importing build
from langflow.api.build import _output_meta_for_vertex
from lfx.graph import Graph


def measure(size, shape):
    """Compare full dictionaries against the old scan before timing nine samples."""
    graph = Graph()
    vertices = [
        SimpleNamespace(
            id=str(i),
            outputs=[{"types": ["Message"]}],
            display_name="Output",
            vertex_type="ChatOutput",
            is_output=i % 2 == 0,
        )
        for i in range(size)
    ]
    by_id = {v.id: v for v in vertices}
    graph.vertices = vertices
    graph.get_vertex = by_id.__getitem__
    graph.successor_map = (
        {str(i): [str(i + 1)] for i in range(size - 1)}
        if shape == "chain"
        else {"0": [str(i) for i in range(1, size - 1)], **{str(i): [str(size - 1)] for i in range(1, size - 1)}}
    )

    def old(vertex_id):
        vertex = graph.get_vertex(vertex_id)
        return {
            "component_id": vertex.id,
            "display_name": vertex.display_name or vertex.vertex_type,
            "vertex_type": vertex.vertex_type,
            "is_output": bool(vertex.is_output),
            "is_terminal": vertex_id in set(graph.get_terminal_nodes()),
            "output_types": vertex.outputs[0].get("types", []),
        }

    for successors in (graph.successor_map.copy(), {}, {"0": ["1"]}):
        graph.successor_map = successors
        for vertex in vertices:
            if old(vertex.id) != _output_meta_for_vertex(graph, vertex.id):
                msg = "Output metadata differs from the scan implementation"
                raise RuntimeError(msg)
    graph.successor_map = (
        {str(i): [str(i + 1)] for i in range(size - 1)}
        if shape == "chain"
        else {"0": [str(i) for i in range(1, size - 1)], **{str(i): [str(size - 1)] for i in range(1, size - 1)}}
    )
    samples = {}
    for name, helper in (("scan", old), ("indexed", lambda vid: _output_meta_for_vertex(graph, vid))):
        values = []
        for _ in range(9):
            start = perf_counter()
            for vertex in vertices:
                helper(vertex.id)
            values.append((perf_counter() - start) * 1000)
        samples[name] = {"samples_ms": values, "median_ms": median(values)}
    return {"vertices": size, "shape": shape, **samples}


if __name__ == "__main__":
    for shape in ("chain", "fan"):
        for size in (10, 100, 800, 2000):
            print(json.dumps(measure(size, shape)))
