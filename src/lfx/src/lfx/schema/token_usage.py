"""Shared token usage extraction and accumulation functions.

Centralizes token usage extraction from LangChain message objects (AIMessage, streaming chunks)
to eliminate duplication across Component, LCModelComponent, and TokenUsageCallbackHandler.
"""

from __future__ import annotations

from lfx.schema.properties import Usage


def _normalize_usage_metadata(um) -> Usage:
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


def extract_usage_from_message(message) -> Usage | None:
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
    # Strategy 1: usage_metadata (LangChain standard)
    usage_metadata = getattr(message, "usage_metadata", None)
    if usage_metadata and isinstance(usage_metadata, dict):
        input_tokens = usage_metadata.get("input_tokens", 0) or 0
        output_tokens = usage_metadata.get("output_tokens", 0) or 0
        if input_tokens or output_tokens:
            return Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )

    response_metadata = getattr(message, "response_metadata", None)
    if not response_metadata:
        return None

    # Strategy 2: response_metadata["token_usage"] (OpenAI format)
    if "token_usage" in response_metadata:
        token_usage = response_metadata["token_usage"]
        return Usage(
            input_tokens=token_usage.get("prompt_tokens"),
            output_tokens=token_usage.get("completion_tokens"),
            total_tokens=token_usage.get("total_tokens"),
        )

    # Strategy 3: response_metadata["usage"] (Anthropic format)
    if "usage" in response_metadata:
        usage = response_metadata["usage"]
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens or 0) + (output_tokens or 0) if input_tokens or output_tokens else None,
        )

    return None


def extract_usage_from_chunk(chunk) -> Usage | None:
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
    """Accumulate usage data across multiple chunks.

    Some providers (e.g. Anthropic) split usage across chunks:
    message_start has input_tokens, message_delta has output_tokens.

    Args:
        existing: Previously accumulated usage, or None.
        new: New usage from the current chunk, or None.

    Returns:
        Accumulated Usage, or None if both inputs are None.
    """
    if new is None:
        return existing
    if existing is None:
        return new

    input_tokens = existing.input_tokens or 0
    output_tokens = existing.output_tokens or 0

    new_input = new.input_tokens or 0
    new_output = new.output_tokens or 0

    if new_input:
        input_tokens += new_input
    if new_output:
        output_tokens += new_output

    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
