"""LangFlow Components module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components import (
        Notion,
        agentql,
        agents,
        aiml,
        amazon,
        anthropic,
        apify,
        arxiv,
        assemblyai,
        azure,
        baidu,
        bing,
        cleanlab,
        cloudflare,
        cohere,
        composio,
        confluence,
        crewai,
        custom_component,
        data,
        datastax,
        deepseek,
        docling,
        duckduckgo,
        embeddings,
        exa,
        firecrawl,
        git,
        glean,
        google,
        groq,
        helpers,
        homeassistant,
        huggingface,
        ibm,
        icosacomputing,
        input_output,
        langchain_utilities,
        langwatch,
        lmstudio,
        logic,
        maritalk,
        mem0,
        mistral,
        models,
        needle,
        notdiamond,
        novita,
        nvidia,
        olivya,
        ollama,
        openai,
        openrouter,
        perplexity,
        processing,
        prototypes,
        redis,
        sambanova,
        scrapegraph,
        searchapi,
        serpapi,
        tavily,
        tools,
        twelvelabs,
        unstructured,
        vectorstores,
        vertexai,
        wikipedia,
        wolframalpha,
        xai,
        yahoosearch,
        youtube,
        zep,
    )

_dynamic_imports = {
    "agents": "lfx.components.agents",
    "data": "lfx.components.data",
    "processing": "lfx.components.processing",
    "vectorstores": "lfx.components.vectorstores",
    "tools": "lfx.components.tools",
    "models": "lfx.components.models",
    "embeddings": "lfx.components.embeddings",
    "helpers": "lfx.components.helpers",
    "input_output": "lfx.components.input_output",
    "logic": "lfx.components.logic",
    "custom_component": "lfx.components.custom_component",
    "prototypes": "lfx.components.prototypes",
    "openai": "lfx.components.openai",
    "anthropic": "lfx.components.anthropic",
    "google": "lfx.components.google",
    "azure": "lfx.components.azure",
    "huggingface": "lfx.components.huggingface",
    "ollama": "lfx.components.ollama",
    "groq": "lfx.components.groq",
    "cohere": "lfx.components.cohere",
    "mistral": "lfx.components.mistral",
    "deepseek": "lfx.components.deepseek",
    "nvidia": "lfx.components.nvidia",
    "amazon": "lfx.components.amazon",
    "vertexai": "lfx.components.vertexai",
    "xai": "lfx.components.xai",
    "perplexity": "lfx.components.perplexity",
    "openrouter": "lfx.components.openrouter",
    "lmstudio": "lfx.components.lmstudio",
    "sambanova": "lfx.components.sambanova",
    "maritalk": "lfx.components.maritalk",
    "novita": "lfx.components.novita",
    "olivya": "lfx.components.olivya",
    "notdiamond": "lfx.components.notdiamond",
    "needle": "lfx.components.needle",
    "cloudflare": "lfx.components.cloudflare",
    "baidu": "lfx.components.baidu",
    "aiml": "lfx.components.aiml",
    "ibm": "lfx.components.ibm",
    "langchain_utilities": "lfx.components.langchain_utilities",
    "crewai": "lfx.components.crewai",
    "composio": "lfx.components.composio",
    "mem0": "lfx.components.mem0",
    "datastax": "lfx.components.datastax",
    "cleanlab": "lfx.components.cleanlab",
    "langwatch": "lfx.components.langwatch",
    "icosacomputing": "lfx.components.icosacomputing",
    "homeassistant": "lfx.components.homeassistant",
    "agentql": "lfx.components.agentql",
    "assemblyai": "lfx.components.assemblyai",
    "twelvelabs": "lfx.components.twelvelabs",
    "docling": "lfx.components.docling",
    "unstructured": "lfx.components.unstructured",
    "redis": "lfx.components.redis",
    "zep": "lfx.components.zep",
    "bing": "lfx.components.bing",
    "duckduckgo": "lfx.components.duckduckgo",
    "serpapi": "lfx.components.serpapi",
    "searchapi": "lfx.components.searchapi",
    "tavily": "lfx.components.tavily",
    "exa": "lfx.components.exa",
    "glean": "lfx.components.glean",
    "yahoosearch": "lfx.components.yahoosearch",
    "apify": "lfx.components.apify",
    "arxiv": "lfx.components.arxiv",
    "confluence": "lfx.components.confluence",
    "firecrawl": "lfx.components.firecrawl",
    "git": "lfx.components.git",
    "wikipedia": "lfx.components.wikipedia",
    "youtube": "lfx.components.youtube",
    "scrapegraph": "lfx.components.scrapegraph",
    "Notion": "lfx.components.Notion",
    "wolframalpha": "lfx.components.wolframalpha",
}

__all__: list[str] = [
    "Notion",
    "agentql",
    "agents",
    "aiml",
    "amazon",
    "anthropic",
    "apify",
    "arxiv",
    "assemblyai",
    "azure",
    "baidu",
    "bing",
    "cleanlab",
    "cloudflare",
    "cohere",
    "composio",
    "confluence",
    "crewai",
    "custom_component",
    "data",
    "datastax",
    "deepseek",
    "docling",
    "duckduckgo",
    "embeddings",
    "exa",
    "firecrawl",
    "git",
    "glean",
    "google",
    "groq",
    "helpers",
    "homeassistant",
    "huggingface",
    "ibm",
    "icosacomputing",
    "input_output",
    "langchain_utilities",
    "langwatch",
    "lmstudio",
    "logic",
    "maritalk",
    "mem0",
    "mistral",
    "models",
    "needle",
    "notdiamond",
    "novita",
    "nvidia",
    "olivya",
    "ollama",
    "openai",
    "openrouter",
    "perplexity",
    "processing",
    "prototypes",
    "redis",
    "sambanova",
    "scrapegraph",
    "searchapi",
    "serpapi",
    "tavily",
    "tools",
    "twelvelabs",
    "unstructured",
    "vectorstores",
    "vertexai",
    "wikipedia",
    "wolframalpha",
    "xai",
    "yahoosearch",
    "youtube",
    "zep",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import component modules on attribute access.

    Args:
        attr_name (str): The attribute/module name to import.

    Returns:
        Any: The imported module or attribute.

    Raises:
        AttributeError: If the attribute is not a known component or cannot be imported.
    """
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        # Use import_mod as in LangChain, passing the module name and package
        result = import_mod(attr_name, "__module__", __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result  # Cache for future access
    return result


def __dir__() -> list[str]:
    """Return list of available attributes for tab-completion and dir()."""
    return list(__all__)


# Optional: Consistency check (can be removed in production)
_missing = set(__all__) - set(_dynamic_imports)
if _missing:
    msg = f"Missing dynamic import mapping for: {', '.join(_missing)}"
    raise ImportError(msg)
