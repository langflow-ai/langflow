"""LangFlow Components module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from langflow.components import (
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
    "agents": "langflow.components.agents",
    "data": "langflow.components.data",
    "processing": "langflow.components.processing",
    "vectorstores": "langflow.components.vectorstores",
    "tools": "langflow.components.tools",
    "models": "langflow.components.models",
    "embeddings": "langflow.components.embeddings",
    "helpers": "langflow.components.helpers",
    "input_output": "langflow.components.input_output",
    "logic": "langflow.components.logic",
    "custom_component": "langflow.components.custom_component",
    "prototypes": "langflow.components.prototypes",
    "openai": "langflow.components.openai",
    "anthropic": "langflow.components.anthropic",
    "google": "langflow.components.google",
    "azure": "langflow.components.azure",
    "huggingface": "langflow.components.huggingface",
    "ollama": "langflow.components.ollama",
    "groq": "langflow.components.groq",
    "cohere": "langflow.components.cohere",
    "mistral": "langflow.components.mistral",
    "deepseek": "langflow.components.deepseek",
    "nvidia": "langflow.components.nvidia",
    "amazon": "langflow.components.amazon",
    "vertexai": "langflow.components.vertexai",
    "xai": "langflow.components.xai",
    "perplexity": "langflow.components.perplexity",
    "openrouter": "langflow.components.openrouter",
    "lmstudio": "langflow.components.lmstudio",
    "sambanova": "langflow.components.sambanova",
    "maritalk": "langflow.components.maritalk",
    "novita": "langflow.components.novita",
    "olivya": "langflow.components.olivya",
    "notdiamond": "langflow.components.notdiamond",
    "needle": "langflow.components.needle",
    "cloudflare": "langflow.components.cloudflare",
    "baidu": "langflow.components.baidu",
    "aiml": "langflow.components.aiml",
    "ibm": "langflow.components.ibm",
    "langchain_utilities": "langflow.components.langchain_utilities",
    "crewai": "langflow.components.crewai",
    "composio": "langflow.components.composio",
    "mem0": "langflow.components.mem0",
    "datastax": "langflow.components.datastax",
    "cleanlab": "langflow.components.cleanlab",
    "langwatch": "langflow.components.langwatch",
    "icosacomputing": "langflow.components.icosacomputing",
    "homeassistant": "langflow.components.homeassistant",
    "agentql": "langflow.components.agentql",
    "assemblyai": "langflow.components.assemblyai",
    "twelvelabs": "langflow.components.twelvelabs",
    "docling": "langflow.components.docling",
    "unstructured": "langflow.components.unstructured",
    "redis": "langflow.components.redis",
    "zep": "langflow.components.zep",
    "bing": "langflow.components.bing",
    "duckduckgo": "langflow.components.duckduckgo",
    "serpapi": "langflow.components.serpapi",
    "searchapi": "langflow.components.searchapi",
    "tavily": "langflow.components.tavily",
    "exa": "langflow.components.exa",
    "glean": "langflow.components.glean",
    "yahoosearch": "langflow.components.yahoosearch",
    "apify": "langflow.components.apify",
    "arxiv": "langflow.components.arxiv",
    "confluence": "langflow.components.confluence",
    "firecrawl": "langflow.components.firecrawl",
    "git": "langflow.components.git",
    "wikipedia": "langflow.components.wikipedia",
    "youtube": "langflow.components.youtube",
    "scrapegraph": "langflow.components.scrapegraph",
    "Notion": "langflow.components.Notion",
    "wolframalpha": "langflow.components.wolframalpha",
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
    "vectara",
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
