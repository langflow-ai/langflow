"""Models & Agents components."""

from lfx.components._importing import import_mod

__all__ = [
    "AgentComponent",
    "BatchRunComponent",
    "EmbeddingModelComponent",
    "LanguageModelComponent",
    "LLMRouterComponent",
    "MCPToolsComponent",
    "MemoryComponent",
    "PromptComponent",
    "StructuredOutputComponent",
]


def __getattr__(name: str):
    if name == "AgentComponent":
        return import_mod("AgentComponent", "agent", __name__)
    if name == "MCPToolsComponent":
        return import_mod("MCPToolsComponent", "mcp_component", __name__)
    if name == "MemoryComponent":
        return import_mod("MemoryComponent", "memory", __name__)
    if name == "PromptComponent":
        return import_mod("PromptComponent", "prompt", __name__)
    if name == "LanguageModelComponent":
        return import_mod("LanguageModelComponent", "language_model", __name__)
    if name == "EmbeddingModelComponent":
        return import_mod("EmbeddingModelComponent", "embedding_model", __name__)
    if name == "LLMRouterComponent":
        return import_mod("LLMRouterComponent", "llm_router", __name__)
    if name == "StructuredOutputComponent":
        return import_mod("StructuredOutputComponent", "structured_output", __name__)
    if name == "BatchRunComponent":
        return import_mod("BatchRunComponent", "batch_run", __name__)
    
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)