"""Import-absence assertions guarding the lfx cold-start path.

Each test class targets a specific heavy module set (pandas/numpy, PIL,
langchain_core/classic) and asserts those modules are NOT present in
``sys.modules`` after a chosen lfx import. The mechanism is a fresh
subprocess + ``sys.modules`` inspection: pytest has already imported
these heavy modules via other fixtures in the current process, so only
a clean interpreter gives a trustworthy signal.
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


class TestLfxImportsWithoutPandas:
    """pandas/numpy are not loaded at module scope across the Graph hot path.

    The previous behavior loaded pandas (~200-400 ms) and numpy (~50-100 ms)
    on every cold boot via several modules on the Graph import chain.
    """

    DEFERRED_MODULES = (
        "lfx.serialization.serialization",
        "lfx.graph.vertex.param_handler",
        "lfx.custom.custom_component.component",
        "lfx.base.tools.component_tool",
        "lfx.schema.schema",
        "lfx.inputs.inputs",
        "lfx.base.data.base_file",
    )

    HEAVY = frozenset({"pandas", "numpy"})

    def test_pandas_numpy_absent_from_deferred_modules(self):
        for module in self.DEFERRED_MODULES:
            _assert_modules_absent(f"import {module}", set(self.HEAVY))

    def test_pandas_numpy_absent_from_helpers_data(self):
        # `lfx.helpers.data` previously did an eager `from lfx.schema.dataframe import DataFrame`
        # which masked the wins on the Graph path; that import is now deferred.
        _assert_modules_absent("import lfx.helpers.data", set(self.HEAVY))

    def test_pandas_numpy_absent_from_graph_hot_path(self):
        # `from lfx.graph.graph.base import Graph` is the critical entry point
        # for `lfx run <flow>`. This is the cumulative assertion across the
        # entire Graph cold path.
        _assert_modules_absent("from lfx.graph.graph.base import Graph", set(self.HEAVY))


class TestFieldTypingDefersLangchainCore:
    """Field-typing constants and the Graph hot path defer langchain imports.

    Importing `lfx.field_typing.constants` does not pull langchain_core or
    langchain_classic, and `from lfx.graph.graph.base import Graph` stays
    clean of them too.
    """

    HEAVY = frozenset({"langchain_core", "langchain_classic", "langchain_text_splitters"})

    def test_constants_import_does_not_pull_langchain(self):
        _assert_modules_absent("import lfx.field_typing.constants", set(self.HEAVY))

    def test_constants_import_does_not_pull_langchain_via_field_typing(self):
        # `from lfx.field_typing import Tool` currently triggers constants load
        # via the existing lazy dispatch; this asserts that path is also clean.
        _assert_modules_absent("import lfx.field_typing", set(self.HEAVY))

    def test_custom_validate_import_does_not_pull_langchain(self):
        _assert_modules_absent("import lfx.custom.validate", set(self.HEAVY))

    def test_tools_package_import_does_not_pull_langchain(self):
        _assert_modules_absent("import lfx.components.tools", set(self.HEAVY))

    def test_langchain_absent_from_graph_hot_path(self):
        _assert_modules_absent("from lfx.graph.graph.base import Graph", set(self.HEAVY))


class TestLfxImportsWithoutPIL:
    """PIL is not loaded at module scope on the Graph hot path.

    PIL was previously pulled via `lfx.schema.image` and `lfx.interface.utils`,
    both of which sit on the Graph import chain through `lfx.schema.message`
    and `lfx.interface.*`. PIL init costs roughly 50 ms on cold imports.
    """

    PIL_MODULES = ("lfx.schema.image", "lfx.interface.utils")
    PIL_PKG = frozenset({"PIL"})

    def test_pil_absent_from_deferred_modules(self):
        for module in self.PIL_MODULES:
            _assert_modules_absent(f"import {module}", set(self.PIL_PKG))

    def test_pil_absent_from_graph_hot_path(self):
        _assert_modules_absent("from lfx.graph.graph.base import Graph", set(self.PIL_PKG))
