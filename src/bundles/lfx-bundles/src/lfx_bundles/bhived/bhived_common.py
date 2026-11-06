"""Shared pieces for the bhived components.

bhived is a shared lesson network for AI agents: an agent searches fixes, known
mistakes and version updates that other agents verified, and writes back what it
verifies itself. Both components call the hosted API at ``https://mcp.bhived.ai``
through the ``bhived`` SDK.

The host is fixed, and the API key always comes from the component's own input.
The SDK would otherwise fall back to ``BHIVED_API_KEY`` or ``~/.bhived/config.json``
on the server, which would send the operator's key on behalf of every flow.
"""

from __future__ import annotations

from typing import Any

from bhived import DEFAULT_API_URL, AsyncBhivedClient, BhivedConfig

DOCUMENTATION_URL = "https://bhived.ai/docs/integrations/langflow"
DEFAULT_TIMEOUT_SECONDS = 30.0
USER_AGENT = "langflow"

API_KEY_INFO = "Your bhived API key, from `npx bhived setup` or the bhived console."  # pragma: allowlist secret
MISSING_KEY_ERROR = "Enter a bhived API key."


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def make_client(api_key: str, timeout: Any) -> AsyncBhivedClient:
    """A client pinned to the hosted API and to this component's key."""
    seconds = float(timeout or DEFAULT_TIMEOUT_SECONDS)
    config = BhivedConfig(api_key=api_key, api_url=DEFAULT_API_URL, timeout=seconds)
    return AsyncBhivedClient(config=config, user_agent=USER_AGENT)


def error_text(exc: Exception, api_key: str) -> str:
    """The error message, with the key masked in case a response ever echoes it."""
    text = str(exc) or type(exc).__name__
    return text.replace(api_key, "***") if api_key else text
