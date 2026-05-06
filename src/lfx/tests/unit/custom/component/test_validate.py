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
