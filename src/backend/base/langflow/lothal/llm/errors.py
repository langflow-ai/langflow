"""Typed errors for the Lothal LLM bridge (Story 0.1).

Story 0.1 requires `call_llm` to "raise a clear typed error on bad config/
connection". Catch `LLMError` for any failure, or a specific subclass to tell a
misconfiguration apart from a runtime/connection fault.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for every error raised by the Lothal LLM bridge."""


class LLMConfigError(LLMError):
    """Configuration or input is missing/invalid.

    Raised for an unset/unknown provider, an unusable provider environment, or a
    malformed `messages` list — anything wrong *before* a model is contacted.
    """


class LLMConnectionError(LLMError):
    """The model call itself failed or returned nothing usable."""
