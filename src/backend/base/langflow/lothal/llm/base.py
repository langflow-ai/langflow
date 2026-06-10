"""Provider-agnostic contract for the Lothal LLM bridge (Story 0.1).

`call_llm` (see `caller.py`) talks only to this interface, so a new model or
service is added by writing one `LLMProvider` subclass and registering it with
`@register_provider` — `call_llm` and every phase engine above it stay
unchanged (open/closed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from langflow.lothal.llm.errors import LLMConfigError

# A chat message in the OpenAI-style shape every Lothal engine already speaks:
# {"role": "system" | "user" | "assistant", "content": "..."}.
Message = dict[str, Any]

VALID_ROLES = frozenset({"system", "user", "assistant"})


def validate_messages(messages: list[Message]) -> None:
    """Validate the shared message shape before any provider runs.

    Raises `LLMConfigError` (a typed error, per Story 0.1) on anything a
    provider cannot be expected to handle: an empty list, a non-dict entry, a
    role outside system/user/assistant, or missing/blank `content`.
    """
    if not messages:
        msg = "`messages` must be a non-empty list."
        raise LLMConfigError(msg)
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            msg = f"message[{i}] must be a dict, got {type(message).__name__}."
            raise LLMConfigError(msg)
        role = message.get("role")
        if role not in VALID_ROLES:
            msg = f"message[{i}] has invalid role {role!r}; expected one of {sorted(VALID_ROLES)}."
            raise LLMConfigError(msg)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            msg = f"message[{i}] must have non-empty string `content`."
            raise LLMConfigError(msg)


class LLMProvider(ABC):
    """One concrete model/service `call_llm` can route to.

    A subclass sets a unique `name`, builds itself from the environment via
    `from_env`, and turns a message list into a single assistant reply in
    `complete`. Decorate it with `@register_provider` (see `registry.py`) to
    make it selectable by name.
    """

    name: ClassVar[str]

    @classmethod
    @abstractmethod
    def from_env(cls) -> LLMProvider:
        """Construct the provider from environment configuration."""

    @abstractmethod
    async def complete(self, messages: list[Message], **kwargs: Any) -> str:
        """Return the assistant reply for `messages` as a non-empty string.

        `call_llm` forwards a per-call `model=` (and any other passthrough
        `kwargs`) here; a provider should honour `model` as an override of its
        own env default.
        """
