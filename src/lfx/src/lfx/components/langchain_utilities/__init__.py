from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .character import CharacterTextSplitterComponent
    from .conversation import ConversationChainComponent
    from .csv_agent import CSVAgentComponent
    from .fake_embeddings import FakeEmbeddingsComponent
    from .html_link_extractor import HtmlLinkExtractorComponent
    from .json_agent import JsonAgentComponent
    from .langchain_hub import LangChainHubPromptComponent
    from .language_recursive import LanguageRecursiveTextSplitterComponent
    from .language_semantic import SemanticTextSplitterComponent
    from .llm_checker import LLMCheckerChainComponent
    from .llm_math import LLMMathChainComponent
    from .natural_language import NaturalLanguageTextSplitterComponent
    from .openai_tools import OpenAIToolsAgentComponent
    from .openapi import OpenAPIAgentComponent
    from .recursive_character import RecursiveCharacterTextSplitterComponent
    from .retrieval_qa import RetrievalQAComponent
    from .runnable_executor import RunnableExecComponent
    from .self_query import SelfQueryRetrieverComponent
    from .spider import SpiderTool
    from .sql import SQLAgentComponent
    from .sql_database import SQLDatabaseComponent
    from .sql_generator import SQLGeneratorComponent
    from .tool_calling import ToolCallingAgentComponent
    from .vector_store_info import VectorStoreInfoComponent
    from .vector_store_router import VectorStoreRouterAgentComponent
    from .xml_agent import XMLAgentComponent

_dynamic_imports = {
    "CharacterTextSplitterComponent": "character",
    "ConversationChainComponent": "conversation",
    "CSVAgentComponent": "csv_agent",
    "FakeEmbeddingsComponent": "fake_embeddings",
    "HtmlLinkExtractorComponent": "html_link_extractor",
    "JsonAgentComponent": "json_agent",
    "LangChainHubPromptComponent": "langchain_hub",
    "LanguageRecursiveTextSplitterComponent": "language_recursive",
    "LLMCheckerChainComponent": "llm_checker",
    "LLMMathChainComponent": "llm_math",
    "NaturalLanguageTextSplitterComponent": "natural_language",
    "OpenAIToolsAgentComponent": "openai_tools",
    "OpenAPIAgentComponent": "openapi",
    "RecursiveCharacterTextSplitterComponent": "recursive_character",
    "RetrievalQAComponent": "retrieval_qa",
    "RunnableExecComponent": "runnable_executor",
    "SelfQueryRetrieverComponent": "self_query",
    "SemanticTextSplitterComponent": "language_semantic",
    "SpiderTool": "spider",
    "SQLAgentComponent": "sql",
    "SQLDatabaseComponent": "sql_database",
    "SQLGeneratorComponent": "sql_generator",
    "ToolCallingAgentComponent": "tool_calling",
    "VectorStoreInfoComponent": "vector_store_info",
    "VectorStoreRouterAgentComponent": "vector_store_router",
    "XMLAgentComponent": "xml_agent",
}

__all__ = [
    "CSVAgentComponent",
    "CharacterTextSplitterComponent",
    "ConversationChainComponent",
    "FakeEmbeddingsComponent",
    "HtmlLinkExtractorComponent",
    "JsonAgentComponent",
    "LLMCheckerChainComponent",
    "LLMMathChainComponent",
    "LangChainHubPromptComponent",
    "LanguageRecursiveTextSplitterComponent",
    "NaturalLanguageTextSplitterComponent",
    "OpenAIToolsAgentComponent",
    "OpenAPIAgentComponent",
    "RecursiveCharacterTextSplitterComponent",
    "RetrievalQAComponent",
    "RunnableExecComponent",
    "SQLAgentComponent",
    "SQLDatabaseComponent",
    "SQLGeneratorComponent",
    "SelfQueryRetrieverComponent",
    "SemanticTextSplitterComponent",
    "SpiderTool",
    "ToolCallingAgentComponent",
    "VectorStoreInfoComponent",
    "VectorStoreRouterAgentComponent",
    "XMLAgentComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import langchain utility components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
