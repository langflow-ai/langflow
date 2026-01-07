"""CometAPI model constants and configuration.

This module contains the default model names available through CometAPI.
These models are used as fallbacks when the API is unavailable or when
no API key is provided.
"""

from typing import Final

# CometAPI available model list based on actual API offerings
COMETAPI_MODELS: Final[list[str]] = [
    # GPT series
    "gpt-5-chat-latest",
    "chatgpt-4o-latest",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4.1",
    "gpt-4o-mini",
    "o4-mini-2025-04-16",
    "o3-pro-2025-06-10",
    # Claude series
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-1-20250805",
    "claude-opus-4-1-20250805-thinking",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-20250514-thinking",
    "claude-3-7-sonnet-latest",
    "claude-3-5-haiku-latest",
    # Gemini series
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    # Grok series
    "grok-4-0709",
    "grok-3",
    "grok-3-mini",
    "grok-2-image-1212",
    # DeepSeek series
    "deepseek-v3.1",
    "deepseek-v3",
    "deepseek-r1-0528",
    "deepseek-chat",
    "deepseek-reasoner",
    # Qwen series
    "qwen3-30b-a3b",
    "qwen3-coder-plus-2025-07-22",
]

# Backward compatibility alias
MODEL_NAMES: Final[list[str]] = COMETAPI_MODELS
