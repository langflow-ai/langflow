"""Committed import-absence assertions for Phase 3 import-deferral plans.

Each IMP-0X wave-1 plan adds its own test class. The mechanism is subprocess
+ `-X importtime` (per CONTEXT.md D-04 and RESEARCH.md Pattern: Import-Absence
Assertion). Subprocess is mandatory because pytest has already imported these
heavy modules via other test fixtures in the current process; only a fresh
interpreter gives a trustworthy signal.

The triggers are chosen to exercise the actual cold-start hot path. `import lfx`
alone is too shallow: the bare package import does not pull serialization.py,
graph.base, or the other modules that eagerly load pandas/numpy/PIL. The hot
path that `lfx run <flow>` walks through goes via `lfx.graph.graph.base.Graph`,
so that is the canonical trigger for IMP-02/IMP-03 detection.
"""

from __future__ import annotations

import subprocess
import sys

# The Graph class is the canonical hot-path entry point for `lfx run <flow>`.
# Importing it transitively loads lfx.graph.schema -> lfx.serialization.serialization
# and lfx.graph.vertex.* -> param_handler + custom_component.component, which is
# precisely where pandas/numpy/PIL are eagerly imported today (per CONCERNS.md §1.1).
GRAPH_IMPORT = "from lfx.graph.graph.base import Graph"


class TestIMP02NoPandas:
    """IMP-02: neither pandas nor numpy is loaded when the Graph hot path is imported."""

    def test_pandas_not_imported_by_graph(self):
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-X", "importtime", "-c", GRAPH_IMPORT],
            capture_output=True,
            timeout=30,
            check=True,
        )
        stderr = result.stderr.decode("utf-8", errors="replace")
        assert "pandas" not in stderr, f"pandas imported on `{GRAPH_IMPORT}`; last 2000 stderr chars:\n{stderr[-2000:]}"

    def test_numpy_not_imported_by_graph(self):
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-X", "importtime", "-c", GRAPH_IMPORT],
            capture_output=True,
            timeout=30,
            check=True,
        )
        stderr = result.stderr.decode("utf-8", errors="replace")
        assert "numpy" not in stderr, f"numpy imported on `{GRAPH_IMPORT}`; last 2000 stderr chars:\n{stderr[-2000:]}"
