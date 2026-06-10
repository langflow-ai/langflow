"""Claude provider — drives the Claude Agent SDK (`claude-agent-sdk`).

Story 0.1's first concrete provider. It reuses the Claude Code subscription's
OAuth credentials (no metered `ANTHROPIC_API_KEY` required); see
`scripts/claude_sdk_subscription.py` for the standalone reference this mirrors.

The Agent SDK takes a single prompt plus a system prompt, so a multi-turn
`messages` list is folded into one labelled transcript here. A future
native-multi-turn provider (e.g. an OpenAI-compatible one) would map `messages`
directly instead — the mapping is per-provider by design.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from langflow.lothal.llm.base import LLMProvider, Message
from langflow.lothal.llm.errors import LLMConfigError, LLMConnectionError
from langflow.lothal.llm.registry import register_provider

if TYPE_CHECKING:
    from types import ModuleType


@register_provider
class ClaudeAgentProvider(LLMProvider):
    """Calls Claude through the Claude Agent SDK / Claude Code runtime."""

    name = "claude"
    # Current flagship; override with the backlog's LOTHAL_MODEL_NAME knob.
    DEFAULT_MODEL = "claude-opus-4-8"

    def __init__(self, model: str) -> None:
        # The default model for this provider; a per-call `model=` overrides it.
        self.model = model

    @classmethod
    def from_env(cls) -> ClaudeAgentProvider:
        model = os.getenv("LOTHAL_MODEL_NAME") or cls.DEFAULT_MODEL
        return cls(model=model)

    async def complete(self, messages: list[Message], *, model: str | None = None, **_: Any) -> str:
        system_prompt, prompt = _to_agent_input(messages)
        sdk = _import_sdk()
        options = sdk.ClaudeAgentOptions(
            model=model or self.model,
            system_prompt=system_prompt or None,
            allowed_tools=[],  # pure text Q&A — no filesystem/bash access
        )
        parts: list[str] = []
        try:
            async for message in sdk.query(prompt=prompt, options=options):
                if isinstance(message, sdk.AssistantMessage):
                    parts.extend(block.text for block in message.content if isinstance(block, sdk.TextBlock))
        except Exception as exc:  # SDK / runtime / connection faults
            msg = f"Claude Agent SDK call failed: {exc}"
            raise LLMConnectionError(msg) from exc
        text = "".join(parts).strip()
        if not text:
            msg = "Claude returned an empty response."
            raise LLMConnectionError(msg)
        return text


def _import_sdk() -> ModuleType:
    """Import `claude_agent_sdk`, mapping a missing install to a typed config error."""
    try:
        import claude_agent_sdk
    except ImportError as exc:
        msg = (
            "The `claude-agent-sdk` package is required for the Claude provider. "
            "Install it (`uv add claude-agent-sdk`) and log into Claude Code."
        )
        raise LLMConfigError(msg) from exc
    return claude_agent_sdk


def _to_agent_input(messages: list[Message]) -> tuple[str, str]:
    """Split `messages` into `(system_prompt, prompt)` for the Agent SDK.

    System turns are concatenated into the system prompt. A lone user turn is
    sent verbatim; any history is rendered as a `User:`/`Assistant:` transcript
    ending on the latest user turn, which the model continues.
    """
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    convo = [m for m in messages if m.get("role") in ("user", "assistant")]
    if not convo:
        msg = "`messages` must contain at least one user or assistant turn."
        raise LLMConfigError(msg)
    system_prompt = "\n\n".join(system_parts)
    if len(convo) == 1 and convo[0]["role"] == "user":
        prompt = convo[0]["content"]
    else:
        labels = {"user": "User", "assistant": "Assistant"}
        lines = [f"{labels[m['role']]}: {m['content']}" for m in convo]
        lines.append("Assistant:")
        prompt = "\n\n".join(lines)
    return system_prompt, prompt
