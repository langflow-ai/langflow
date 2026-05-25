"""Import-absence assertions specific to the Graph construction path.

The cold-start refactor's central claim is that constructing a `Graph` and
walking its build pipeline does not pull langchain / transformers / torch
into `sys.modules` until a component actually references those symbols at
execute time. This file targets the graph-construction surface specifically;
``test_import_absence.py`` covers the lfx-package import surface.

Each test runs in a fresh subprocess (pytest collection has already imported
heavy modules into the current interpreter, so a clean child is the only
trustworthy probe).
"""

from __future__ import annotations

import subprocess
import sys

_CHECK_SCRIPT = """
import sys
{import_stmt}
loaded = sorted(m for m in sys.modules if m in {check_set!r})
if loaded:
    sys.stderr.write('LOADED:' + ','.join(loaded) + chr(10))
    sys.exit(1)
"""


def _assert_modules_absent(import_stmt: str, check: set[str]) -> None:
    """Run import_stmt in a fresh interpreter and assert none of `check` are in sys.modules."""
    script = _CHECK_SCRIPT.format(import_stmt=import_stmt, check_set=check)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        msg = f"Expected none of {sorted(check)} in sys.modules after `{import_stmt}`; stderr:\n{stderr}"
        raise AssertionError(msg)


class TestGraphConstructionDoesNotPullHeavyImports:
    """`Graph` construction stays clean of langchain / transformers / torch.

    The pre-cold-start branch imported langchain_core, langchain_classic, and
    transformers (which transitively pulls torch) through field-typing
    constants and the validate module. Cold-start moves those behind
    `_LazyImportProxy`, so Graph imports and Graph instantiation must not
    touch any of them. If they show up here, the lazy contract is broken on
    the graph construction path even though the lfx-package-level test in
    test_import_absence.py still passes.
    """

    HEAVY = frozenset(
        {
            "langchain_core",
            "langchain_classic",
            "langchain_text_splitters",
            "langchain_community",
            "transformers",
            "torch",
        }
    )

    def test_graph_class_import_clean(self):
        _assert_modules_absent("from lfx.graph.graph.base import Graph", set(self.HEAVY))

    def test_graph_payload_helpers_import_clean(self):
        # Graph.from_payload is the entry point that langflow-base and the
        # Assistant feature route through. Importing the helper module must
        # not eagerly pull langchain.
        _assert_modules_absent("from lfx.graph.graph import utils", set(self.HEAVY))

    def test_empty_graph_instance_clean(self):
        # Constructing a Graph instance with no vertices is still expected to
        # stay off the langchain path. The vertex builder must not import
        # langchain just to exist.
        _assert_modules_absent(
            "from lfx.graph.graph.base import Graph\ng = Graph()\n",
            set(self.HEAVY),
        )

    def test_vertex_module_import_clean(self):
        # `lfx.graph.vertex.base` is on every Graph construction path; it
        # holds `Vertex.instantiate_component` which calls into
        # `loading.instantiate_class` and ultimately into `validate.create_class`.
        # The class itself must not import langchain at module load.
        _assert_modules_absent("from lfx.graph.vertex.base import Vertex", set(self.HEAVY))
