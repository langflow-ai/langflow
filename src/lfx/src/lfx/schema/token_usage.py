"""Shared token usage extraction and accumulation functions.

Centralizes token usage extraction from LangChain message objects (AIMessage, streaming chunks)
to eliminate duplication across Component, LCModelComponent, and TokenUsageCallbackHandler.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lfx.schema.properties import Usage


def _normalize_usage_metadata(um: Any) -> Usage:
    """Extract usage from usage_metadata, handling both dict (TypedDict) and object forms."""
    if isinstance(um, dict):
        return Usage(
            input_tokens=um.get("input_tokens"),
            output_tokens=um.get("output_tokens"),
            total_tokens=um.get("total_tokens"),
        )
    return Usage(
        input_tokens=getattr(um, "input_tokens", None),
        output_tokens=getattr(um, "output_tokens", None),
        total_tokens=getattr(um, "total_tokens", None),
    )


def extract_usage_from_message(message: Any) -> Usage | None:
    """Extract token usage from an AIMessage's metadata.

    Tries three strategies in priority order:
    1. usage_metadata (LangChain standard, works for Ollama and newer providers)
    2. response_metadata["token_usage"] (OpenAI format)
    3. response_metadata["usage"] (Anthropic format)

    Args:
        message: An AIMessage or similar object with usage_metadata/response_metadata.

    Returns:
        Usage with token counts, or None if no usage data is available.
    """

    def from_counts(data: Mapping[str, Any], input_key: str, output_key: str) -> Usage | None:
        input_tokens = data.get(input_key)
        output_tokens = data.get(output_key)
        total_tokens = data.get("total_tokens")
        if all(value is None for value in (input_tokens, output_tokens, total_tokens)):
            return None
        if total_tokens is None and (input_tokens is not None or output_tokens is not None):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)
        return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)

    usage_metadata = getattr(message, "usage_metadata", None)
    if isinstance(usage_metadata, dict) and (usage := from_counts(usage_metadata, "input_tokens", "output_tokens")):
        return usage

    response_metadata = getattr(message, "response_metadata", None) or {}
    if not isinstance(response_metadata, Mapping):
        return None
    for name, input_key, output_key in (
        ("token_usage", "prompt_tokens", "completion_tokens"),
        ("usage", "input_tokens", "output_tokens"),
    ):
        data = response_metadata.get(name)
        if isinstance(data, Mapping) and (usage := from_counts(data, input_key, output_key)):
            return usage
    return None


def extract_usage_from_llm_result(response: Any) -> Usage | None:
    """Extract token usage from an LLMResult object.

    Consolidates the extraction logic used by both the token usage tracking feature
    (TokenUsageCallbackHandler) and the traces feature (NativeCallbackHandler) into
    a single source of truth.

    Tries four strategies in priority order:
    1. llm_output["token_usage"] (legacy OpenAI path, LLMResult-specific)
    2. generations[].message via extract_usage_from_message() (usage_metadata, response_metadata)
    3. generations[].generation_info["token_usage"] or ["usage"] (older Anthropic adapters)

    Args:
        response: An LLMResult or similar object with llm_output and generations attributes.

    Returns:
        Usage with token counts, or None if no usage data is available.
    """
    # Strategy 1: llm_output["token_usage"] (legacy OpenAI, only on LLMResult)
    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict) and "token_usage" in llm_output:
        token_usage = llm_output["token_usage"]
        if isinstance(token_usage, dict):
            input_tokens = token_usage.get("prompt_tokens", 0) or 0
            output_tokens = token_usage.get("completion_tokens", 0) or 0
            if input_tokens or output_tokens:
                return Usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                )

    # Iterate generations for message-level and generation_info extraction
    generations = getattr(response, "generations", None) or []
    for generation_list in generations:
        for generation in generation_list:
            # Strategy 2: delegate to extract_usage_from_message() for standard paths
            message = getattr(generation, "message", None)
            if message is not None:
                usage = extract_usage_from_message(message)
                if usage:
                    return usage

            # Strategy 3: generation_info fallback (older Anthropic adapters)
            gen_info = getattr(generation, "generation_info", None) or {}
            if isinstance(gen_info, dict):
                usage_dict = gen_info.get("token_usage") or gen_info.get("usage")
                if isinstance(usage_dict, dict):
                    input_tokens = usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens") or 0
                    output_tokens = usage_dict.get("completion_tokens") or usage_dict.get("output_tokens") or 0
                    if input_tokens or output_tokens:
                        return Usage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=input_tokens + output_tokens,
                        )

    return None


def extract_usage_from_chunk(chunk: Any) -> Usage | None:
    """Extract token usage from a streaming chunk.

    Handles both usage_metadata and response_metadata formats on streaming chunks.

    Args:
        chunk: A streaming chunk (AIMessageChunk or similar).

    Returns:
        Usage with token counts from this chunk, or None if no usage data.
    """
    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
        return _normalize_usage_metadata(chunk.usage_metadata)

    if hasattr(chunk, "response_metadata") and chunk.response_metadata:
        metadata = chunk.response_metadata
        if "token_usage" in metadata:
            return Usage(
                input_tokens=metadata["token_usage"].get("prompt_tokens"),
                output_tokens=metadata["token_usage"].get("completion_tokens"),
                total_tokens=metadata["token_usage"].get("total_tokens"),
            )
        if "usage" in metadata:
            return Usage(
                input_tokens=metadata["usage"].get("input_tokens"),
                output_tokens=metadata["usage"].get("output_tokens"),
                total_tokens=None,
            )

    return None


def accumulate_usage(existing: Usage | None, new: Usage | None) -> Usage | None:
    """Accumulate usage data across multiple chunks using max-based merge.

    Uses max() per field instead of addition to handle both provider styles:
    - Anthropic splits usage across chunks (input on start, output on delta) —
      max picks each field's value from the chunk that carries it.
    - OpenAI may send cumulative totals on multiple chunks — max picks the
      latest (largest) value without double-counting.

    Args:
        existing: Previously accumulated usage, or None.
        new: New usage from the current chunk, or None.

    Returns:
        Merged Usage, or None if both inputs are None.
    """
    if new is None:
        return existing
    if existing is None:
        return new

    input_tokens = max(existing.input_tokens or 0, new.input_tokens or 0)
    output_tokens = max(existing.output_tokens or 0, new.output_tokens or 0)

    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
