from textwrap import dedent

import pytest
from lfx.custom.validate import _get_module_fallbacks, _resolve_attribute, create_class


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
