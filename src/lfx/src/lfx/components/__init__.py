from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    # These imports are only for type checking and match _dynamic_imports
    from lfx.components import (
        FAISS,
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
        cassandra,
        chains,
        chroma,
        cleanlab,
        clickhouse,
        cloudflare,
        cohere,
        composio,
        confluence,
        couchbase,
        crewai,
        custom_component,
        data,
        datastax,
        deactivated,
        deepseek,
        docling,
        documentloaders,
        duckduckgo,
        elastic,
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
        jigsawstack,
        langchain_utilities,
        langwatch,
        link_extractors,
        lmstudio,
        logic,
        maritalk,
        mem0,
        milvus,
        mistral,
        models,
        models_and_agents,
        mongodb,
        needle,
        notdiamond,
        novita,
        nvidia,
        olivya,
        ollama,
        openai,
        openrouter,
        output_parsers,
        perplexity,
        pgvector,
        pinecone,
        processing,
        prototypes,
        qdrant,
        redis,
        sambanova,
        scrapegraph,
        searchapi,
        serpapi,
        supabase,
        tavily,
        textsplitters,
        toolkits,
        tools,
        twelvelabs,
        unstructured,
        upstash,
        vectara,
        vectorstores,
        vertexai,
        vlmrun,
        weaviate,
        wikipedia,
        wolframalpha,
        xai,
        yahoosearch,
        youtube,
        zep,
    )


# Dynamic imports mapping - maps both modules and individual components
_dynamic_imports = {
    # Category modules (existing functionality)
    "agentql": "__module__",
    "agents": "__module__",
    "aiml": "__module__",
    "amazon": "__module__",
    "anthropic": "__module__",
    "apify": "__module__",
    "arxiv": "__module__",
    "assemblyai": "__module__",
    "azure": "__module__",
    "baidu": "__module__",
    "bing": "__module__",
    "cassandra": "__module__",
    "chains": "__module__",
    "chroma": "__module__",
    "cleanlab": "__module__",
    "clickhouse": "__module__",
    "cloudflare": "__module__",
    "cohere": "__module__",
    "composio": "__module__",
    "confluence": "__module__",
    "couchbase": "__module__",
    "crewai": "__module__",
    "custom_component": "__module__",
    "data": "__module__",
    "datastax": "__module__",
    "deactivated": "__module__",
    "deepseek": "__module__",
    "docling": "__module__",
    "documentloaders": "__module__",
    "duckduckgo": "__module__",
    "elastic": "__module__",
    "embeddings": "__module__",
    "exa": "__module__",
    "FAISS": "__module__",
    "firecrawl": "__module__",
    "git": "__module__",
    "glean": "__module__",
    "google": "__module__",
    "groq": "__module__",
    "helpers": "__module__",
    "homeassistant": "__module__",
    "huggingface": "__module__",
    "ibm": "__module__",
    "icosacomputing": "__module__",
    "input_output": "__module__",
    "jigsawstack": "__module__",
    "langchain_utilities": "__module__",
    "langwatch": "__module__",
    "link_extractors": "__module__",
    "lmstudio": "__module__",
    "logic": "__module__",
    "maritalk": "__module__",
    "mem0": "__module__",
    "milvus": "__module__",
    "mistral": "__module__",
    "models": "__module__",
    "models_and_agents": "__module__",
    "mongodb": "__module__",
    "needle": "__module__",
    "notdiamond": "__module__",
    "Notion": "__module__",
    "novita": "__module__",
    "nvidia": "__module__",
    "olivya": "__module__",
    "ollama": "__module__",
    "openai": "__module__",
    "openrouter": "__module__",
    "output_parsers": "__module__",
    "perplexity": "__module__",
    "pgvector": "__module__",
    "pinecone": "__module__",
    "processing": "__module__",
    "prototypes": "__module__",
    "qdrant": "__module__",
    "redis": "__module__",
    "sambanova": "__module__",
    "scrapegraph": "__module__",
    "searchapi": "__module__",
    "serpapi": "__module__",
    "supabase": "__module__",
    "tavily": "__module__",
    "textsplitters": "__module__",
    "toolkits": "__module__",
    "tools": "__module__",
    "twelvelabs": "__module__",
    "unstructured": "__module__",
    "upstash": "__module__",
    "vectara": "__module__",
    "vectorstores": "__module__",
    "vertexai": "__module__",
    "vlmrun": "__module__",
    "weaviate": "__module__",
    "wikipedia": "__module__",
    "wolframalpha": "__module__",
    "xai": "__module__",
    "yahoosearch": "__module__",
    "youtube": "__module__",
    "zep": "__module__",
}

# Track which modules we've already discovered to avoid re-scanning
_discovered_modules = set()


def _discover_components_from_module(module_name):
    """Discover individual components from a specific module on-demand."""
    if module_name in _discovered_modules or module_name == "Notion":
        return

    try:
        # Try to import the module and get its dynamic imports
        module = import_mod(module_name, "__module__", __spec__.parent)

        if hasattr(module, "_dynamic_imports"):
            # Add each component from this module to our main mapping
            for comp_name, comp_file in module._dynamic_imports.items():
                # Create the full path: module_name.comp_file
                _dynamic_imports[comp_name] = f"{module_name}.{comp_file}"
                # Note: We don't add component names to __all__ since they are classes, not modules
                # __all__ should only contain module names, individual components are accessible via __getattr__

        _discovered_modules.add(module_name)

    except (ImportError, AttributeError):
        # If import fails, mark as discovered to avoid retrying
        _discovered_modules.add(module_name)


# Static base __all__ with module names
__all__ = [
    "FAISS",
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
    "cassandra",
    "chains",
    "chroma",
    "cleanlab",
    "clickhouse",
    "cloudflare",
    "cohere",
    "composio",
    "confluence",
    "couchbase",
    "crewai",
    "custom_component",
    "data",
    "datastax",
    "deactivated",
    "deepseek",
    "docling",
    "documentloaders",
    "duckduckgo",
    "elastic",
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
    "jigsawstack",
    "langchain_utilities",
    "langwatch",
    "link_extractors",
    "lmstudio",
    "logic",
    "maritalk",
    "mem0",
    "milvus",
    "mistral",
    "models",
    "models_and_agents",
    "mongodb",
    "needle",
    "notdiamond",
    "novita",
    "nvidia",
    "olivya",
    "ollama",
    "openai",
    "openrouter",
    "output_parsers",
    "perplexity",
    "pgvector",
    "pinecone",
    "processing",
    "prototypes",
    "qdrant",
    "redis",
    "sambanova",
    "scrapegraph",
    "searchapi",
    "serpapi",
    "supabase",
    "tavily",
    "textsplitters",
    "toolkits",
    "tools",
    "twelvelabs",
    "unstructured",
    "upstash",
    "vectara",
    "vectorstores",
    "vertexai",
    "vlmrun",
    "weaviate",
    "wikipedia",
    "wolframalpha",
    "xai",
    "yahoosearch",
    "youtube",
    "zep",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import component modules or individual components on attribute access.

    Supports both:
    - components.agents (module access)
    - components.AgentComponent (direct component access)

    Uses on-demand discovery - only scans modules when components are requested.
    """
    # First check if we already know about this attribute
    if attr_name not in _dynamic_imports:
        # Try to discover components from modules that might have this component
        # Get all module names we haven't discovered yet
        undiscovered_modules = [
            name
            for name in _dynamic_imports
            if _dynamic_imports[name] == "__module__" and name not in _discovered_modules and name != "Notion"
        ]

        # Discover components from undiscovered modules
        # Try all undiscovered modules until we find the component or exhaust the list
        for module_name in undiscovered_modules:
            _discover_components_from_module(module_name)
            # Check if we found what we're looking for
            if attr_name in _dynamic_imports:
                break

    # If still not found, raise AttributeError
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

    try:
        module_path = _dynamic_imports[attr_name]

        if module_path == "__module__":
            # This is a module import (e.g., components.agents)
            result = import_mod(attr_name, "__module__", __spec__.parent)
            # After importing a module, discover its components
            _discover_components_from_module(attr_name)
        elif "." in module_path:
            # This is a component import (e.g., components.AgentComponent -> agents.agent)
            module_name, component_file = module_path.split(".", 1)
            # Check if this is an alias module (agents, data, helpers, logic, models)
            # These modules forward to other modules, so we need to import directly from the module
            # instead of trying to import from a submodule that doesn't exist
            if module_name in ("agents", "data", "helpers", "logic", "models"):
                # For alias modules, import the module and get the component directly
                alias_module = import_mod(module_name, "__module__", __spec__.parent)
                result = getattr(alias_module, attr_name)
            else:
                # Import the specific component from its module
                result = import_mod(attr_name, component_file, f"{__spec__.parent}.{module_name}")
        else:
            # Fallback to regular import
            result = import_mod(attr_name, module_path, __spec__.parent)

    except (ImportError, AttributeError) as e:
        # Check if this is a missing dependency issue by looking at the error message
        if "No module named" in str(e):
            # Extract the missing module name and suggest installation
            import re

            match = re.search(r"No module named '([^']+)'", str(e))
            if match:
                missing_module = match.group(1)
                msg = f"Could not import '{attr_name}' from '{__name__}'. Missing dependency: '{missing_module}'. "
            else:
                msg = f"Could not import '{attr_name}' from '{__name__}'. Missing dependencies: {e}"
        elif "cannot import name" in str(e):
            msg = f"Could not import '{attr_name}' from '{__name__}'. Import error: {e}"
        else:
            msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e

    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
