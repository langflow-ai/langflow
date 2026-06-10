#!/usr/bin/env python3
"""Call Claude from a script using your Claude Code subscription (no metered API key).

This uses the **Claude Agent SDK** (`claude-agent-sdk`), which drives the bundled
Claude Code runtime. When you're logged into Claude Code with a Pro/Max plan, the
SDK reuses that subscription's OAuth credentials automatically — you are NOT billed
per-token against an ANTHROPIC_API_KEY.

Setup
-----
    pip install claude-agent-sdk        # or: uv add claude-agent-sdk
    # You're already logged in (the `claude` CLI is installed & authenticated).
    # If not:  claude   ->  /login

    # IMPORTANT: a set ANTHROPIC_API_KEY silently OVERRIDES the subscription.
    # Unset it to bill against the subscription instead of a metered key:
    unset ANTHROPIC_API_KEY

Run
---
    python scripts/claude_sdk_subscription.py "Explain what a Langflow flow is in 2 sentences."

Headless / CI (no interactive login available)
----------------------------------------------
    claude setup-token                  # prints a long-lived OAuth token
    export CLAUDE_CODE_OAUTH_TOKEN=...   # the SDK will use it as the subscription
"""

from __future__ import annotations

import asyncio
import os
import sys

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

# Current flagship model. Requires a recent SDK + Claude Code runtime; fall back to
# "claude-opus-4-7" / "claude-sonnet-4-6" if your installed version is older.
MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = "You are a concise, helpful assistant. Answer directly."


async def ask(prompt: str) -> None:
    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=[],  # pure text Q&A — no filesystem/bash access
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print()  # newline after the streamed answer
            cost = message.total_cost_usd
            # NOTE: this is the *notional* token cost the SDK computes — it is reported
            # regardless of billing path. On a Pro/Max subscription it is informational
            # only (covered by the plan); it does NOT mean you were charged this amount.
            if cost is not None:
                print(f"\n[notional token cost: ${cost:.4f} (informational; covered by your plan)]")


def main() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "WARNING: ANTHROPIC_API_KEY is set — it overrides your subscription and "
            "will bill per-token. `unset ANTHROPIC_API_KEY` to use the Pro/Max plan.\n",
            file=sys.stderr,
        )

    prompt = " ".join(sys.argv[1:]) or "Say hello and tell me which model you are."
    asyncio.run(ask(prompt))


if __name__ == "__main__":
    main()
