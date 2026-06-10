"""Lothal LLM bridge (Epic 0).

A reusable, provider-agnostic server-side bridge every phase engine plugs into.

Public surface::

    call_llm(messages, *, provider=None, **kwargs) -> str   # Story 0.1
    LLMProvider, register_provider, get_provider, available_providers
    LLMError, LLMConfigError, LLMConnectionError

Add a model or service by subclassing `LLMProvider` and decorating it with
`@register_provider`; nothing above this package changes. The default provider
is Claude via the Claude Agent SDK (see `providers/claude.py`).
"""

from langflow.lothal.llm.base import LLMProvider, Message, validate_messages
from langflow.lothal.llm.caller import call_llm
from langflow.lothal.llm.errors import LLMConfigError, LLMConnectionError, LLMError
from langflow.lothal.llm.registry import available_providers, get_provider, register_provider

__all__ = [
    "LLMConfigError",
    "LLMConnectionError",
    "LLMError",
    "LLMProvider",
    "Message",
    "available_providers",
    "call_llm",
    "get_provider",
    "register_provider",
    "validate_messages",
]
