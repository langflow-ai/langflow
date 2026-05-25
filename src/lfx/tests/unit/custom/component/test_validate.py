import ast
import sys
from textwrap import dedent

import pytest
from lfx.custom.validate import (
    _get_module_fallbacks,
    _LazyExecGlobals,
    _LazyImportProxy,
    _resolve_attribute,
    create_class,
    create_function,
    execute_function,
    prepare_global_scope,
)


def test_importing_langflow_module_in_lfx():
    code = dedent("""from langflow.custom import   Component
class TestComponent(Component):
    def some_method(self):
        pass
    """)
    result = create_class(code, "TestComponent")
    assert result.__name__ == "TestComponent"


def test_importing_langflow_logging_in_lfx():
    """Test that langflow.logging can be imported in lfx context without errors."""
    code = dedent("""
from langflow.logging import logger, configure
from langflow.custom import Component

class TestLoggingComponent(Component):
    def some_method(self):
        # Test that both logger and configure work
        configure(log_level="INFO")
        logger.info("Test message from component")
        return "success"
    """)
    result = create_class(code, "TestLoggingComponent")
    assert result.__name__ == "TestLoggingComponent"


def test_create_class_future_annotations_with_type_checking():
    """Regression test for issue #12776.

     `from __future__ import annotations` must act as a compiler directive so that TYPE_CHECKING-only
    imports don't raise NameError at classdefinition time.
    """
    code = dedent("""
from __future__ import annotations
from typing import TYPE_CHECKING
from langflow.custom import Component

if TYPE_CHECKING:
    from typing import List

class TypeCheckingComponent(Component):
    display_name = "Test"

    def build(self, value: List[str]) -> str:
        return str(value)
    """)
    result = create_class(code, "TypeCheckingComponent")
    assert result.__name__ == "TypeCheckingComponent"
    # With PEP 563 active, annotations should be stored as strings rather than evaluated
    hints = result.build.__annotations__
    assert hints.get("value") == "List[str]"
    assert hints.get("return") == "str"


def test_execute_function_supports_aliased_dotted_imports():
    code = dedent("""
import urllib.request as request

def to_url(path):
    return request.pathname2url(path)
""")
    assert execute_function(code, "to_url", "folder name/file.txt") == "folder%20name/file.txt"


def test_execute_function_supports_non_aliased_dotted_imports():
    """Regression test: `import urllib.request` then using `urllib.request.X` in execute_function."""
    code = dedent("""
import urllib.request

def to_url(path):
    return urllib.request.pathname2url(path)
""")
    assert execute_function(code, "to_url", "folder name/file.txt") == "folder%20name/file.txt"


def test_execute_function_supports_deep_dotted_imports():
    """Ensure 3+ level dotted imports work (e.g., import xml.etree.ElementTree)."""
    code = dedent("""
import xml.etree.ElementTree

def make_root(tag):
    return xml.etree.ElementTree.Element(tag).tag
""")
    assert execute_function(code, "make_root", "root") == "root"


def test_create_function_supports_dotted_imports():
    code = dedent("""
import urllib.request

def to_url(path):
    return urllib.request.pathname2url(path)
""")
    func = create_function(code, "to_url")
    assert func("folder name/file.txt") == "folder%20name/file.txt"


def test_prepare_global_scope_keeps_top_level_package_for_dotted_imports():
    module = ast.parse(
        dedent("""
import urllib.request

def to_url(path):
    return urllib.request.pathname2url(path)
""")
    )
    scope = prepare_global_scope(module)

    assert "urllib" in scope
    assert scope["urllib"].request.pathname2url("folder name/file.txt") == "folder%20name/file.txt"


def test_prepare_global_scope_supports_aliased_from_imports():
    """Regression test: `from X import Y as Z` must bind Z in scope, not Y."""
    module = ast.parse(
        dedent("""
from urllib.request import pathname2url as to_url_path

def to_url(path):
    return to_url_path(path)
""")
    )
    scope = prepare_global_scope(module)

    assert "to_url_path" in scope
    assert "pathname2url" not in scope
    assert scope["to_url_path"]("folder name/file.txt") == "folder%20name/file.txt"


def test_create_class_supports_aliased_from_imports():
    """End-to-end: a component using `from X import Y as Z` should load and Z is usable."""
    code = dedent("""
from urllib.request import pathname2url as to_url_path
from lfx.custom import Component

class AliasedImportComponent(Component):
    def to_url(self, path):
        return to_url_path(path)
""")
    cls = create_class(code, "AliasedImportComponent")
    assert cls.__name__ == "AliasedImportComponent"
    assert cls().to_url("folder name/file.txt") == "folder%20name/file.txt"


# ---------------------------------------------------------------------------
# _get_module_fallbacks
# ---------------------------------------------------------------------------
class TestGetModuleFallbacks:
    def test_no_fallback_for_unrelated_module(self):
        assert _get_module_fallbacks("requests") == ["requests"]

    def test_langflow_falls_back_to_lfx(self):
        result = _get_module_fallbacks("langflow.custom")
        assert result == ["langflow.custom", "lfx.custom"]

    def test_langflow_deep_path(self):
        result = _get_module_fallbacks("langflow.custom.validate")
        assert result == ["langflow.custom.validate", "lfx.custom.validate"]

    def test_langchain_falls_back_to_langchain_classic(self):
        result = _get_module_fallbacks("langchain.memory")
        assert result == ["langchain.memory", "langchain_classic.memory"]

    def test_langchain_deep_path(self):
        result = _get_module_fallbacks("langchain.chains.base")
        assert result == ["langchain.chains.base", "langchain_classic.chains.base"]

    def test_langchain_community_not_remapped(self):
        assert _get_module_fallbacks("langchain_community.tools") == ["langchain_community.tools"]

    def test_langchain_core_not_remapped(self):
        assert _get_module_fallbacks("langchain_core.messages") == ["langchain_core.messages"]

    def test_bare_langchain_no_fallback(self):
        assert _get_module_fallbacks("langchain") == ["langchain"]

    def test_bare_langflow_no_fallback(self):
        assert _get_module_fallbacks("langflow") == ["langflow"]

    def test_only_first_occurrence_replaced(self):
        result = _get_module_fallbacks("langchain.langchain.nested")
        assert result == ["langchain.langchain.nested", "langchain_classic.langchain.nested"]

    def test_original_always_first(self):
        """The original module is always tried first."""
        for name in ["langflow.custom", "langchain.agents", "requests"]:
            assert _get_module_fallbacks(name)[0] == name


# ---------------------------------------------------------------------------
# _resolve_attribute
# ---------------------------------------------------------------------------
class TestResolveAttribute:
    # -- attributes that exist in langchain 1.0 (no fallback needed) --

    def test_resolves_existing_attribute(self):
        import langchain.agents as mod

        result = _resolve_attribute(mod, "langchain.agents", "create_react_agent")
        assert result is not None

    def test_resolves_existing_tool_attribute(self):
        import langchain.tools as mod

        result = _resolve_attribute(mod, "langchain.tools", "tool")
        assert callable(result)

    # -- attributes removed in langchain 1.0 (attribute-level fallback) --

    def test_falls_back_for_agent_executor(self):
        import langchain.agents as mod
        from langchain_classic.agents import AgentExecutor

        result = _resolve_attribute(mod, "langchain.agents", "AgentExecutor")
        assert result is AgentExecutor

    def test_falls_back_for_base_single_action_agent(self):
        import langchain.agents as mod
        from langchain_classic.agents import BaseSingleActionAgent

        result = _resolve_attribute(mod, "langchain.agents", "BaseSingleActionAgent")
        assert result is BaseSingleActionAgent

    def test_falls_back_for_structured_tool(self):
        import langchain.tools as mod
        from langchain_classic.tools import StructuredTool

        result = _resolve_attribute(mod, "langchain.tools", "StructuredTool")
        assert result is StructuredTool

    # -- non-langchain modules should not fall back --

    def test_no_fallback_for_non_langchain_module(self):
        import os

        with pytest.raises(ImportError, match="Cannot import name 'nonexistent'"):
            _resolve_attribute(os, "os", "nonexistent")

    def test_no_fallback_for_langchain_core(self):
        """langchain_core is not remapped to langchain_classic."""
        import langchain_core.messages as mod

        with pytest.raises((ImportError, AttributeError)):
            _resolve_attribute(mod, "langchain_core.messages", "TotallyFakeClass")

    # -- truly missing attributes should still raise --

    def test_missing_attribute_in_both_raises(self):
        import langchain.agents as mod

        with pytest.raises((ImportError, AttributeError, ModuleNotFoundError)):
            _resolve_attribute(mod, "langchain.agents", "CompletelyFakeClassName")


# ---------------------------------------------------------------------------
# create_class backwards compatibility (end-to-end through prepare_global_scope)
# ---------------------------------------------------------------------------
class TestLangchainClassicBackwardsCompat:
    """Test that old flows with pre-1.0 langchain imports still load."""

    # -- removed modules (module-level fallback) --

    def test_from_langchain_memory(self):
        code = dedent("""
from langchain.memory import ConversationBufferMemory
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return ConversationBufferMemory
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_schema(self):
        code = dedent("""
from langchain.schema import AgentAction
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return AgentAction
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_chains(self):
        code = dedent("""
from langchain.chains.base import Chain
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return Chain
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_callbacks(self):
        code = dedent("""
from langchain.callbacks.base import BaseCallbackHandler
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return BaseCallbackHandler
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_llms(self):
        code = dedent("""
from langchain.llms.base import BaseLLM
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return BaseLLM
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_prompts(self):
        code = dedent("""
from langchain.prompts import PromptTemplate
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return PromptTemplate
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_output_parsers(self):
        code = dedent("""
from langchain.output_parsers import PydanticOutputParser
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return PydanticOutputParser
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_text_splitter(self):
        code = dedent("""
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return RecursiveCharacterTextSplitter
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_document_loaders(self):
        code = dedent("""
from langchain.document_loaders.base import BaseLoader
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return BaseLoader
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_retrievers(self):
        code = dedent("""
from langchain.retrievers import ContextualCompressionRetriever
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return ContextualCompressionRetriever
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_vectorstores(self):
        code = dedent("""
from langchain.vectorstores.base import VectorStore
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return VectorStore
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    # -- existing modules with removed attributes (attribute-level fallback) --

    def test_from_langchain_agents_agent_executor(self):
        code = dedent("""
from langchain.agents import AgentExecutor
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return AgentExecutor
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_from_langchain_tools_structured_tool(self):
        code = dedent("""
from langchain.tools import StructuredTool
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return StructuredTool
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    # -- multiple imports from the same removed module --

    def test_multiple_imports_from_removed_module(self):
        code = dedent("""
from langchain.schema import AgentAction, AgentFinish
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return AgentAction, AgentFinish
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    # -- mixing old and new imports in the same component --

    def test_mixed_old_and_new_imports(self):
        code = dedent("""
from langchain.agents import create_react_agent
from langchain.memory import ConversationBufferMemory
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return create_react_agent, ConversationBufferMemory
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    # -- langchain 1.0 native imports still work --

    def test_langchain_1_0_agents_import(self):
        code = dedent("""
from langchain.agents import create_react_agent
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return create_react_agent
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    def test_langchain_1_0_tools_import(self):
        code = dedent("""
from langchain.tools import tool
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return tool
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"

    # -- langchain_core imports are not affected --

    def test_langchain_core_import_unaffected(self):
        code = dedent("""
from langchain_core.messages import HumanMessage
from langflow.custom import Component

class Comp(Component):
    def run(self):
        return HumanMessage
        """)
        result = create_class(code, "Comp")
        assert result.__name__ == "Comp"


# ---------------------------------------------------------------------------
# prepare_global_scope: lazy / eager binding decisions per-alias
# ---------------------------------------------------------------------------
class TestLazyExecGlobalsBinding:
    """Verify which alias shapes produce `_LazyImportProxy` vs eagerly-resolved bindings."""

    def test_returns_lazy_exec_globals(self):
        scope = prepare_global_scope(ast.parse("class Foo: pass\n"))
        assert isinstance(scope, _LazyExecGlobals)

    def test_non_langchain_module_resolves_eagerly(self):
        # `import json` is outside _LAZY_MODULE_PREFIXES, so the binding must be the real
        # module and not a proxy. Guards against future widening of the prefix list breaking
        # Pydantic-validated string-constant imports.
        scope = prepare_global_scope(ast.parse("import json\n"))
        assert "json" in scope
        assert not isinstance(scope["json"], _LazyImportProxy)
        assert scope["json"] is sys.modules["json"]

    def test_non_langchain_from_import_resolves_eagerly(self):
        scope = prepare_global_scope(ast.parse("from os.path import join\n"))
        assert not isinstance(scope.get("join"), _LazyImportProxy)
        assert callable(scope["join"])

    def test_langchain_from_import_returns_proxy(self):
        scope = prepare_global_scope(ast.parse("from langchain_classic.agents import AgentExecutor\n"))
        assert isinstance(scope["AgentExecutor"], _LazyImportProxy)

    def test_langchain_import_returns_proxy(self):
        scope = prepare_global_scope(ast.parse("import langchain_core\n"))
        assert isinstance(scope["langchain_core"], _LazyImportProxy)

    def test_from_import_asname_lazy(self):
        # `from langchain_classic.agents import AgentExecutor as AE` should bind only `AE`.
        scope = prepare_global_scope(ast.parse("from langchain_classic.agents import AgentExecutor as AE\n"))
        assert "AE" in scope
        assert "AgentExecutor" not in scope
        assert isinstance(scope["AE"], _LazyImportProxy)

    def test_module_import_asname_lazy(self):
        # `import langchain_core as lc` should bind only `lc`.
        scope = prepare_global_scope(ast.parse("import langchain_core as lc\n"))
        assert "lc" in scope
        assert "langchain_core" not in scope
        assert isinstance(scope["lc"], _LazyImportProxy)

    def test_from_import_asname_eager(self):
        # `from os import path as P` is eager because `os` is not in the lazy prefix list.
        scope = prepare_global_scope(ast.parse("from os import path as P\n"))
        assert "P" in scope
        assert not isinstance(scope["P"], _LazyImportProxy)

    def test_mixed_lazy_and_eager_on_single_import_node(self):
        # `import json, langchain_core` is one ast.Import node with two aliases. Each alias
        # must be classified independently: json eager, langchain_core lazy.
        scope = prepare_global_scope(ast.parse("import json, langchain_core\n"))
        assert not isinstance(scope["json"], _LazyImportProxy)
        assert isinstance(scope["langchain_core"], _LazyImportProxy)

    def test_star_import_resolves_eagerly(self):
        # `from X import *` always resolves now, regardless of prefix. Use os.path so the
        # test does not depend on langchain being installed cleanly.
        scope = prepare_global_scope(ast.parse("from os.path import *\n"))
        assert callable(scope.get("join"))
        assert not isinstance(scope["join"], _LazyImportProxy)


class TestLazyImportProxyResolution:
    """Resolution semantics of `_LazyImportProxy` itself."""

    def test_repr_does_not_resolve(self):
        proxy = _LazyImportProxy(
            "definitely_not_a_real_module_xyz",
            "Whatever",
            is_module_binding=False,
            top_level=False,
        )
        text = repr(proxy)
        assert "definitely_not_a_real_module_xyz.Whatever" in text
        assert "definitely_not_a_real_module_xyz" not in sys.modules

    def test_resolve_surfaces_module_not_found(self):
        # Deferred module that truly does not exist must raise ModuleNotFoundError on first
        # use rather than silently producing None or a stale sentinel.
        proxy = _LazyImportProxy(
            "definitely_not_a_real_module_xyz",
            "Whatever",
            is_module_binding=False,
            top_level=False,
        )
        with pytest.raises(ModuleNotFoundError):
            proxy._resolve()

    def test_resolution_is_cached(self):
        # Once resolved, _resolve() must return the same object on every call so callers see
        # consistent identity and avoid repeated import cost on hot paths.
        proxy = _LazyImportProxy(
            "json",
            "loads",
            is_module_binding=False,
            top_level=False,
        )
        first = proxy._resolve()
        second = proxy._resolve()
        assert first is second


class TestLazyImportProxyTorchPrePrime:
    """The pre-prime path inside ``_LazyImportProxy._resolve``.

    torch 2.x has a fragile partial-init order: when first imported nested
    inside another module's ``__init__`` chain (e.g. transformers under
    ``langchain_classic.agents``), Python publishes a half-initialized
    ``sys.modules["torch"]`` whose ``torch.library`` attribute does not yet
    exist, surfacing on Windows + torch 2.x as
    "partially initialized module 'torch' has no attribute 'library' …".

    The fix loads torch top-level *before* the proxy walks the langchain
    chain. These tests assert that torch is the first module loaded when
    resolving a langchain-family proxy, but not loaded when resolving a
    non-langchain proxy. The Windows-specific failure mode itself is not
    reproducible on macOS / Linux dev envs; this test is a regression guard
    on the *mechanism* (which langchain family triggers the pre-prime, in
    what order).
    """

    @pytest.fixture
    def import_module_tracker(self, monkeypatch):
        """Wrap importlib.import_module to record the call order."""
        import importlib as _importlib

        calls: list[str] = []
        real_import = _importlib.import_module

        def tracking_import(name, *args, **kwargs):
            calls.append(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(_importlib, "import_module", tracking_import)
        return calls

    @pytest.mark.parametrize(
        "module_name",
        [
            "langchain_classic.agents",
            "langchain.agents",
            "langchain",  # bare umbrella package -- regression guard for the prefix-vs-segment fix
            "langchain_community.tools",
        ],
    )
    def test_langchain_family_pre_primes_torch(self, import_module_tracker, module_name):
        # Skip cleanly if torch isn't installed in this env — the pre-prime is
        # contextlib.suppress(ImportError) on purpose so absent torch is fine.
        pytest.importorskip("torch")
        # Skip if the langchain family isn't installed — we can't probe what we can't reach.
        pytest.importorskip(module_name.split(".")[0])

        # Module-binding shape (`import X` / `import X.Y`) for plain package names
        # like "langchain" or "langchain_community.tools"; from-import shape
        # (`from langchain[_classic].agents import AgentExecutor`) for the .agents
        # variants where the typical user-component code reaches for a class.
        is_from_import = "agents" in module_name
        proxy = _LazyImportProxy(
            module_name,
            "AgentExecutor" if is_from_import else None,
            is_module_binding=not is_from_import,
            top_level=not is_from_import,
        )
        # Resolution may fail in this env (e.g. AgentExecutor symbol not in
        # langchain.agents directly); the pre-prime ordering is what we're
        # asserting, not successful resolution.
        import contextlib as _contextlib

        with _contextlib.suppress(ImportError, AttributeError):
            proxy._resolve()

        # Only top-level (non-relative) module names matter for ordering: relative
        # imports starting with "." are imported inside an already-running module's
        # __init__ and don't trigger the torch partial-init race.
        absolute = [c for c in import_module_tracker if not c.startswith(".")]
        assert "torch" in absolute, f"torch was never imported; calls were {absolute[:10]}"
        assert module_name in absolute, f"target module not imported; calls were {absolute[:10]}"
        torch_idx = absolute.index("torch")
        target_idx = absolute.index(module_name)
        assert torch_idx < target_idx, (
            f"torch must be imported BEFORE {module_name} to avoid nested partial-init; "
            f"order was {absolute[: max(torch_idx, target_idx) + 1]}"
        )

    def test_non_langchain_proxy_skips_torch_pre_prime(self, import_module_tracker):
        # `import json` is a stdlib module the proxy can resolve eagerly; the
        # langchain pre-prime branch must not fire for it. We don't even require
        # torch to be installed for this assertion.
        proxy = _LazyImportProxy("json", None, is_module_binding=True, top_level=True)
        proxy._resolve()
        assert "torch" not in import_module_tracker, (
            f"Pre-prime fired for a non-langchain module; calls were {import_module_tracker}"
        )

    def test_langchain_core_proxy_skips_torch_pre_prime(self):
        # `langchain_core` is intentionally NOT in the pre-prime set: it does
        # not transitively pull torch (no transformers in its dep tree). The
        # pre-prime is scoped to the langchain umbrella + langchain_classic +
        # langchain_community where the torch import actually happens, so
        # langchain_core resolves like any other module. Regression guard for
        # the first-segment-set membership test in `_resolve`.
        pytest.importorskip("langchain_core")
        import importlib as _importlib

        calls: list[str] = []
        real_import = _importlib.import_module

        def tracking_import(name, *args, **kwargs):
            calls.append(name)
            return real_import(name, *args, **kwargs)

        original = _importlib.import_module
        _importlib.import_module = tracking_import
        try:
            proxy = _LazyImportProxy(
                "langchain_core.messages",
                "AIMessage",
                is_module_binding=False,
                top_level=False,
            )
            import contextlib as _contextlib

            with _contextlib.suppress(ImportError, AttributeError):
                proxy._resolve()
        finally:
            _importlib.import_module = original

        # We don't assert torch is absent (some other test in the session may
        # have loaded it); we assert the pre-prime did NOT fire because the
        # proxy's own _resolve loop never asked importlib for "torch" as a
        # standalone call. The pre-prime is the only path that calls
        # `importlib.import_module("torch")` from inside `_resolve()`.
        assert "torch" not in calls, f"Pre-prime fired for langchain_core; calls were {calls}"


class TestCreateClassAttributeErrorHandler:
    """The ``except AttributeError`` branch in :func:`create_class`.

    Sibling case to the ImportError branch: when proxy resolution surfaces an
    AttributeError (typically torch 2.x partial-init via transformers nested
    under langchain), the generic ``except Exception`` would wrap it as
    "Error creating class. AttributeError(...)" with no signal that the fix is
    environment-level rather than a code typo. The dedicated branch detects
    the partial-init signature and adds an actionable hint.
    """

    def test_partial_init_attribute_error_surfaces_actionable_hint(self, monkeypatch):
        # Force prepare_global_scope to raise the exact AttributeError shape
        # torch produces under partial init. The handler should catch it and
        # add the torch/transformers/langchain hint to the ValueError.
        from lfx.custom import validate as _validate

        partial_init_msg = (
            "partially initialized module 'torch' has no attribute 'library' (most likely due to a circular import)"
        )

        def boom(_module):
            raise AttributeError(partial_init_msg)

        monkeypatch.setattr(_validate, "prepare_global_scope", boom)
        code = dedent("""
            from lfx.custom import Component
            class C(Component):
                display_name = 'x'
        """)
        with pytest.raises(ValueError, match="Attribute error while creating class") as excinfo:
            create_class(code, "C")
        msg = str(excinfo.value)
        assert "partially initialized module" in msg
        # The actionable hint must surface the suggested fix area
        assert "transitive C-extension import" in msg
        assert "torch" in msg

    def test_generic_attribute_error_falls_through_to_generic_handler(self, monkeypatch):
        # An AttributeError that does NOT match the partial-init signature
        # MUST fall through to the generic ``except Exception`` handler so
        # the wrapped message names the real exception type. Catching every
        # AttributeError would mis-direct users with legitimate bugs (e.g.
        # ``self.foo.bar`` where ``foo`` is None) toward a torch/transformers
        # environment fix that has nothing to do with their problem.
        from lfx.custom import validate as _validate

        generic_msg = "some other unrelated attribute error"

        def boom(_module):
            raise AttributeError(generic_msg)

        monkeypatch.setattr(_validate, "prepare_global_scope", boom)
        code = dedent("""
            from lfx.custom import Component
            class C(Component):
                display_name = 'x'
        """)
        with pytest.raises(ValueError, match="Error creating class") as excinfo:
            create_class(code, "C")
        msg = str(excinfo.value)
        # Routed through the generic handler -> "Error creating class. AttributeError(...)".
        assert "AttributeError" in msg, f"expected exception type in wrap, got {msg!r}"
        # The original message must survive the wrap so users see the real failure.
        assert generic_msg in msg, f"original AttributeError message lost in wrap: {msg!r}"
        # And the torch-specific hint must NOT appear for generic AttributeErrors.
        assert "transitive C-extension import" not in msg
        assert "Attribute error while creating class" not in msg


class TestCheckFunctionBodyNameResolution:
    """Static AST pass for undefined-name references inside class method bodies.

    Sub-PR #12786 removed DEFAULT_IMPORT_STRING auto-injection and added an
    actionable NameError hint as compensation. The runtime NameError handler
    only fires for class-body references; this static pass closes the gap for
    method-body references so the hint applies to the common case
    (``def build(self): return AgentExecutor(...)``).
    """

    def test_undefined_langchain_symbol_in_def_body_raises_with_hint(self):
        # QA Fixture A from LE-1229. AgentExecutor referenced inside def build()
        # without an import; release-1.10.0 had DEFAULT_IMPORT_STRING auto-inject
        # AgentExecutor, cold-start removed that, so this is the user-facing
        # case the hint mechanism must catch.
        code = dedent("""
            from lfx.custom import Component
            from lfx.io import Output

            class BadAgentComponent(Component):
                display_name = 'Bad Agent'
                outputs = [Output(display_name='Output', name='output', method='build')]

                def build(self):
                    return AgentExecutor.__name__
        """)
        with pytest.raises(ValueError, match="Name error") as excinfo:
            create_class(code, "BadAgentComponent")
        msg = str(excinfo.value)
        assert "AgentExecutor" in msg
        assert "langchain_classic.agents" in msg, f"hint should name the langchain_classic.agents module: {msg!r}"
        assert "from langchain_classic.agents import AgentExecutor" in msg

    def test_undefined_legacy_lfx_symbol_in_def_body_raises_with_hint(self):
        # Same gap, lfx-side: a symbol from _LEGACY_LFX_IMPORT_HINTS referenced
        # inside def build() without its import line. ``Output`` is one of the
        # 24 legacy lfx names that used to come from DEFAULT_IMPORT_STRING.
        code = dedent("""
            from lfx.custom import Component

            class BadOutputComponent(Component):
                display_name = 'x'
                def build(self):
                    return Output(display_name='o', name='o', method='build')
        """)
        with pytest.raises(ValueError, match="Name error") as excinfo:
            create_class(code, "BadOutputComponent")
        msg = str(excinfo.value)
        assert "Output" in msg
        assert "lfx.io" in msg

    def test_dynamic_runtime_global_passes_silently(self):
        # No-hint-no-flag rule (validate.py inside _check_function_body_name_resolution).
        # A name we don't have a known import target for (could be a graph-level
        # runtime-injected global, monkey-patched base, etc.) must NOT be flagged.
        # Anything else would false-positive the legitimate dynamic-globals use
        # case and refuse otherwise-valid components.
        code = dedent("""
            from lfx.custom import Component

            class DynComponent(Component):
                display_name = 'd'
                def build(self):
                    return some_runtime_injected_global
        """)
        cls = create_class(code, "DynComponent")
        assert cls.__name__ == "DynComponent"

    def test_imported_symbol_in_def_body_passes(self):
        # Sanity check: when the user *does* import the symbol, the static
        # pass must not flag it. The hint table contains the name; the
        # imports must take priority.
        code = dedent("""
            from lfx.custom import Component
            from lfx.io import Output

            class GoodComponent(Component):
                display_name = 'g'
                def build(self):
                    return Output(display_name='o', name='o', method='build')
        """)
        cls = create_class(code, "GoodComponent")
        assert cls.__name__ == "GoodComponent"

    def test_locally_assigned_symbol_in_def_body_passes(self):
        # Locals discovered via `_function_locals` must shadow the hint table.
        # An assignment inside the method body to a name that happens to live
        # in the legacy hint table must not raise.
        code = dedent("""
            from lfx.custom import Component

            class LocalAssignComponent(Component):
                display_name = 'la'
                def build(self):
                    Output = 'overridden'
                    return Output
        """)
        cls = create_class(code, "LocalAssignComponent")
        assert cls.__name__ == "LocalAssignComponent"

    def test_function_parameter_passes(self):
        # Function parameters are locals: a method that takes a parameter
        # named after a hint-table symbol must not be flagged.
        code = dedent("""
            from lfx.custom import Component

            class ParamComponent(Component):
                display_name = 'p'
                def transform(self, Output):
                    return Output
        """)
        cls = create_class(code, "ParamComponent")
        assert cls.__name__ == "ParamComponent"

    def test_except_handler_alias_passes(self):
        # `except E as Output:` binds Output for the handler body. The static
        # pass must collect ExceptHandler.name into locals_ so the reference
        # below doesn't false-positive.
        code = dedent("""
            from lfx.custom import Component

            class ExceptComponent(Component):
                display_name = 'e'
                def build(self):
                    try:
                        x = 1
                    except Exception as Output:
                        return str(Output)
                    return x
        """)
        cls = create_class(code, "ExceptComponent")
        assert cls.__name__ == "ExceptComponent"

    def test_comprehension_iter_variable_passes(self):
        # `[... for Output in xs]` binds Output as a comprehension iterator.
        # _collect_target_names on the generator target must catch this so
        # the Output reference inside the comprehension expression doesn't
        # false-positive.
        code = dedent("""
            from lfx.custom import Component

            class CompComponent(Component):
                display_name = 'c'
                def build(self):
                    return [Output for Output in range(3)]
        """)
        cls = create_class(code, "CompComponent")
        assert cls.__name__ == "CompComponent"

    def test_walrus_operator_binding_passes(self):
        # `if (Output := load()):` binds Output via ast.NamedExpr. Regression
        # guard for the NamedExpr branch in _function_locals.
        code = dedent("""
            from lfx.custom import Component

            class WalrusComponent(Component):
                display_name = 'w'
                def build(self):
                    values = [1, 2, 3]
                    if (Output := values[0]):
                        return Output
                    return None
        """)
        cls = create_class(code, "WalrusComponent")
        assert cls.__name__ == "WalrusComponent"

    def test_nested_function_locals_pass(self):
        # Nested defs inside a method get their own locals_ via the recursive
        # ast.walk; their parameters must not leak undefined-name errors.
        code = dedent("""
            from lfx.custom import Component

            class NestedComponent(Component):
                display_name = 'n'
                def build(self):
                    def helper(Output):
                        return Output
                    return helper('x')
        """)
        cls = create_class(code, "NestedComponent")
        assert cls.__name__ == "NestedComponent"

    def test_with_statement_alias_passes(self):
        # `with ctx() as Output:` binds Output via With.items[].optional_vars.
        code = dedent("""
            import contextlib
            from lfx.custom import Component

            class WithComponent(Component):
                display_name = 'wi'
                def build(self):
                    with contextlib.nullcontext('value') as Output:
                        return Output
        """)
        cls = create_class(code, "WithComponent")
        assert cls.__name__ == "WithComponent"
