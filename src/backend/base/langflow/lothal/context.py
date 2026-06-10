"""Context manager — assembles the chat-completions `messages` array for a turn.

Story 0.2 of the Lothal LLM interface (Epic 0). `build_messages` is the single
seam every phase engine uses to turn stored conversation turns into the
OpenAI-style `messages` payload sent to `call_llm` (Story 0.1). It is a pure
function: no DB or network I/O and no mutation of its inputs — callers load the
history and pass it in.
"""

from __future__ import annotations

from langflow.services.database.models.lothal_project.model import Message, MessageRole

# Our stored role enum → the OpenAI chat-completions role names. Keyed by the
# enum members (str-valued, so they also match the plain strings the ORM stores).
_ROLE_TO_OPENAI: dict[str, str] = {
    MessageRole.USER: "user",
    MessageRole.ASSISTANT: "assistant",
}


def build_messages(
    system_prompt: str,
    history: list[Message],
    user_message: str,
) -> list[dict[str, str]]:
    """Build the chat-completions `messages` array for one conversation turn.

    Order is fixed and total: the `system_prompt` first, then the full `history`
    in order (each turn's stored role mapped to its OpenAI role), then the
    current `user_message` last as a `user` turn.

    Args:
        system_prompt: the phase's system instruction; always the first message.
        history: prior turns, oldest first; `USER` → `user`, `ASSISTANT` →
            `assistant`.
        user_message: the turn the user just sent; appended last.

    Returns:
        A new list of `{"role", "content"}` dicts. Inputs are never mutated.

    Raises:
        ValueError: a history message carries a role outside `USER`/`ASSISTANT`.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for message in history:
        role = _ROLE_TO_OPENAI.get(message.role)
        if role is None:
            supported = ", ".join(sorted(_ROLE_TO_OPENAI)) or "(none)"
            msg = f"Unsupported message role {message.role!r}; expected one of: {supported}."
            raise ValueError(msg)
        messages.append({"role": role, "content": message.content})
    messages.append({"role": "user", "content": user_message})
    return messages
