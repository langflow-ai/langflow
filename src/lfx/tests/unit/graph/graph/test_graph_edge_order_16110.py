"""Regression test for langflow-ai/langflow#16110.

``Graph._build_edges`` previously returned ``list(set(...))``. Because
``Edge.__hash__`` is derived from a ``__repr__`` string, the order of the
resulting list depended on ``PYTHONHASHSEED``: a list input fed by several
sources received those sources' values in a different order on each process.

The fix keeps insertion order via ``dict.fromkeys`` while still deduplicating.
This test rebuilds the same graph under several hash seeds and asserts the edge
order is stable (which is exactly what the deterministic order guarantees).
"""

import os
import subprocess
import sys

import pytest

REPRO_SCRIPT = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph


def main():
    a = ChatInput(_id="A")
    b = ChatOutput(_id="B")
    c = ChatOutput(_id="C")
    g = Graph()
    a_id = g.add_component(a)
    b_id = g.add_component(b)
    c_id = g.add_component(c)
    g.add_component_edge(a_id, (a.outputs[0].name, b.inputs[0].name), b_id)
    g.add_component_edge(a_id, (a.outputs[0].name, c.inputs[0].name), c_id)
    g.prepare()
    return ",".join(e.target_id for e in g.edges)


if __name__ == "__main__":
    print(main())
"""


def test_graph_edge_order_stable_across_hash_seed():
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(REPRO_SCRIPT)
        path = fh.name
    try:
        # Insertion order is A -> B, A -> C, so the edge targets must be B, C.
        for seed in ("0", "1", "123", "9999", "42"):
            proc = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            assert proc.returncode == 0, proc.stderr
            assert proc.stdout.strip() == "B,C", (
                f"edge order unstable under PYTHONHASHSEED={seed}: {proc.stdout!r}"
            )
    finally:
        os.unlink(path)
