"""Token estimates and text caps for the Agent's context budget.

Every limit here is in tokens. A token is estimated at 4 characters, the same estimate as Codex and the
Langflow token callback, so no tokenizer is needed.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4

# Largest tool result that enters the run state, in tokens. A small model window gets a smaller cap.
TOOL_RESULT_CAP_TOKENS = 10_000
TOOL_RESULT_WINDOW_SHARE = 0.25


def tool_result_cap(window: int | None) -> int:
    """The tool result cap for a model window: 10,000 tokens, or a quarter of a smaller window."""
    return min(TOOL_RESULT_CAP_TOKENS, int(window * TOOL_RESULT_WINDOW_SHARE)) if window else TOOL_RESULT_CAP_TOKENS


def estimate_tokens(text: str) -> int:
    """Estimate the tokens of `text` at 4 characters for each token, rounded up."""
    return -(-len(text) // CHARS_PER_TOKEN)


def cap_text(text: str, max_tokens: int) -> str:
    """Return `text` cut to about `max_tokens`, keeping the head and the tail.

    A marker in the middle states how much was cut. Text inside the cap is returned unchanged.
    """
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    cut = len(text) - 2 * half
    marker = f"\n\n[... {cut:,} characters (about {estimate_tokens(text[half:-half]):,} tokens) cut here ...]\n\n"
    return text[:half] + marker + text[-half:]
