"""PraisonAI helper utilities for Langflow integration.

Provides conversion functions for tools, LLMs, and memory configuration
between Langflow and PraisonAI formats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def convert_tools(tools: list | None) -> list[Callable] | None:
    """Convert Langflow/LangChain tools to PraisonAI-compatible callables.

    PraisonAI accepts any callable, so we extract the callable portion
    from LangChain-style tools.

    Args:
        tools: List of tools from Langflow (may be LangChain tools, callables, etc.)

    Returns:
        List of callables compatible with PraisonAI, or None if no tools provided.
    """
    if not tools:
        return None

    converted = []
    for tool in tools:
        if tool is None:
            continue

        # Already a plain callable
        if callable(tool) and not hasattr(tool, "run"):
            converted.append(tool)
        # LangChain StructuredTool or similar with .run method
        elif hasattr(tool, "run") and callable(tool.run):
            converted.append(tool.run)
        # LangChain tool with _run method
        elif hasattr(tool, "_run") and callable(tool._run):
            converted.append(tool._run)
        # Fallback: if it's callable, use it directly
        elif callable(tool):
            converted.append(tool)

    return converted if converted else None


def convert_llm(llm: Any) -> str | None:
    """Convert Langflow LanguageModel to PraisonAI LLM string format.

    PraisonAI uses 'provider/model-name' format (e.g., 'openai/gpt-4o-mini').

    Args:
        llm: LLM from Langflow (could be string, LangChain model, or None)

    Returns:
        String in 'provider/model-name' format, or None if no LLM provided.
    """
    if llm is None:
        return None

    # Already a string (most common case)
    if isinstance(llm, str):
        return llm

    # LangChain model object - extract model name
    if hasattr(llm, "model_name") and llm.model_name:
        model_name = llm.model_name
    elif hasattr(llm, "model") and llm.model:
        model_name = llm.model
    else:
        # Fallback to string representation
        return str(llm)

    # Try to determine provider from LangChain namespace
    provider = None
    if hasattr(llm, "get_lc_namespace"):
        namespace = llm.get_lc_namespace()
        if namespace:
            provider_raw = namespace[0]
            # Remove langchain_ prefix if present
            if provider_raw.startswith("langchain_"):
                provider = provider_raw[10:]

    if provider:
        return f"{provider}/{model_name}"
    return model_name


def build_memory_config(
    memory: bool | dict | None,
    memory_provider: str | None = None,
    memory_config_dict: dict | None = None,
) -> bool | dict:
    """Build PraisonAI MemoryConfig from Langflow inputs.

    Args:
        memory: Simple bool toggle or existing config dict
        memory_provider: Optional provider name (e.g., 'rag', 'mem0')
        memory_config_dict: Optional full MemoryConfig as dict from advanced input

    Returns:
        bool (False/True) or dict (MemoryConfig) for PraisonAI Agent.
    """
    # If full config dict provided, use it
    if memory_config_dict and isinstance(memory_config_dict, dict):
        return memory_config_dict

    # If memory is already a dict, return as-is
    if isinstance(memory, dict):
        return memory

    # Simple bool case
    if not memory:
        return False

    # Memory enabled but no provider specified
    if not memory_provider:
        return True

    # Build config with provider
    return {
        "provider": memory_provider,
    }
