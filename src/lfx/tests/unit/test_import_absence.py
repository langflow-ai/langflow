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


class TestLazyValidateExecGlobals:
    """`_LazyExecGlobals` is the marker type returned by `prepare_global_scope`.

    The class itself is a nominal `dict` subclass — CPython bypasses `__missing__` /
    `__getitem__` on dict subclasses for class-body name lookups (CPython #33128),
    so the laziness lives in the VALUES (`_LazyImportProxy` instances bound by
    `prepare_global_scope` for each deferred import alias), not in the container.
    These tests assert the marker type is preserved across copy() and that
    proxies are actually bound for langchain-family modules.
    """

    def test_lazy_exec_globals_is_dict_subclass(self):
        from lfx.custom.validate import _LazyExecGlobals

        assert issubclass(_LazyExecGlobals, dict)
        instance = _LazyExecGlobals({"a": 1})
        assert isinstance(instance, dict)
        assert instance["a"] == 1

    def test_lazy_exec_globals_copy_preserves_marker_type(self):
        # `dict.copy()` returns a plain dict, which would strip the marker
        # type and silently drop the "this is a lazy scope" signal. Preserve
        # _LazyExecGlobals so nested-exec callers keep the laziness contract.
        from lfx.custom.validate import _LazyExecGlobals

        original = _LazyExecGlobals({"k": "v"})
        copied = original.copy()
        assert isinstance(copied, _LazyExecGlobals)
        assert copied == {"k": "v"}

    def test_prepare_global_scope_returns_lazy_marker(self):
        # No langchain symbols here, so no proxies are bound. The marker type
        # is still expected so downstream code can rely on the contract
        # regardless of which imports the module under exec carries.
        import ast as _ast

        from lfx.custom.validate import _LazyExecGlobals, prepare_global_scope

        module = _ast.parse("import json\n")
        scope = prepare_global_scope(module)
        assert isinstance(scope, _LazyExecGlobals)

    def test_prepare_global_scope_defers_langchain_import(self):
        # `from langchain_classic.agents import AgentExecutor` must bind a
        # _LazyImportProxy, not the real symbol, and must not touch
        # `sys.modules["langchain_classic"]` until something accesses the
        # proxy. Runs in a subprocess to get a clean sys.modules.
        script = (
            "import ast, sys\n"
            "from lfx.custom.validate import prepare_global_scope, _LazyImportProxy\n"
            "mod = ast.parse('from langchain_classic.agents import AgentExecutor\\n')\n"
            "scope = prepare_global_scope(mod)\n"
            "assert isinstance(scope['AgentExecutor'], _LazyImportProxy), type(scope['AgentExecutor'])\n"
            "assert 'langchain_classic' not in sys.modules, sorted(sys.modules)\n"
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            msg = f"prepare_global_scope did not defer langchain_classic import:\n{stderr}"
            raise AssertionError(msg)

    def test_prepare_global_scope_eager_import_resolves(self):
        # Non-langchain imports stay eager so strict Pydantic validators and
        # call sites that expect real objects (e.g. string constants from
        # `lfx.utils.constants`) behave unchanged. `import json` must bind the
        # real module object, not a proxy.
        import ast as _ast

        from lfx.custom.validate import _LazyImportProxy, prepare_global_scope

        module = _ast.parse("import json\n")
        scope = prepare_global_scope(module)
        assert not isinstance(scope["json"], _LazyImportProxy)
        assert scope["json"].dumps({"k": 1}) == '{"k": 1}'
