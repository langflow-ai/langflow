"""Committed import-absence assertions for Phase 3 import-deferral plans.

Each IMP-0X wave-1 plan adds its own test class. The mechanism is subprocess
+ `sys.modules` inspection (per CONTEXT.md D-04 and RESEARCH.md Pattern:
Import-Absence Assertion). Subprocess is mandatory because pytest has already
imported these heavy modules via other test fixtures in the current process;
only a fresh interpreter gives a trustworthy signal.

IMP-02 asserts absence against: (a) each of the 7 modules the plan refactored
in isolation, (b) `lfx.helpers.data` which was deferred as an in-scope masking
dependency, and (c) the full `from lfx.graph.graph.base import Graph` hot path
(which additionally required partial deferrals in
`lfx.field_typing.constants`, `lfx.schema.artifact`, and the DataFrame import
in `lfx.base.data.base_file`, all bundled with IMP-02 per CONTEXT.md D-10).
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


class TestIMP02NoPandas:
    """IMP-02: pandas/numpy are not loaded at module scope across the Graph hot path.

    Targets three scopes:
    1. Each of the 7 modules IMP-02 directly refactored, in isolation.
    2. `lfx.helpers.data`, deferred as an in-scope masking dependency.
    3. The full `from lfx.graph.graph.base import Graph` hot path, which required
       additional partial deferrals bundled with IMP-02 per CONTEXT.md D-10
       (lfx.field_typing.constants, lfx.schema.artifact, lfx.base.data.base_file).
    """

    IMP02_MODULES = (
        "lfx.serialization.serialization",
        "lfx.graph.vertex.param_handler",
        "lfx.custom.custom_component.component",
        "lfx.base.tools.component_tool",
        "lfx.schema.schema",
        "lfx.inputs.inputs",
        "lfx.base.data.base_file",
    )

    HEAVY = frozenset({"pandas", "numpy"})

    def test_pandas_numpy_absent_from_imp02_modules(self):
        for module in self.IMP02_MODULES:
            _assert_modules_absent(f"import {module}", set(self.HEAVY))

    def test_pandas_numpy_absent_from_helpers_data(self):
        # lfx.helpers.data is on the Graph path and was also deferred under IMP-02 scope
        # because its eager `from lfx.schema.dataframe import DataFrame` was masking the wins.
        _assert_modules_absent("import lfx.helpers.data", set(self.HEAVY))

    def test_pandas_numpy_absent_from_graph_hot_path(self):
        # The `lfx run <flow>` critical entry point. Per CONCERNS.md 1.1, this was
        # loading pandas (~200-400ms) and numpy (~50-100ms) on every cold boot.
        _assert_modules_absent("from lfx.graph.graph.base import Graph", set(self.HEAVY))
