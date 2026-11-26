"""Shared, validated settings for the harness form and Agent runtime."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HarnessRuntimeConfig(BaseModel):
    model_config = ConfigDict(strict=True)

    context_strategy: Literal["all", "recent_turns"] = "all"
    context_turns: int = Field(default=8, ge=1, le=10000)
    compaction: Literal["off", "summarize"] = "off"
    compaction_trigger_tokens: int = Field(default=8000, ge=1, le=10000000)
    compaction_keep_messages: int = Field(default=12, ge=1, le=10000)
    max_iterations: int = Field(default=15, ge=1, le=128000)
    tool_policy: Literal["tool_defaults", "ask", "deny"] = "tool_defaults"


def harness_runtime_inputs():
    from lfx.field_typing.range_spec import RangeSpec
    from lfx.inputs.inputs import DropdownInput, IntInput

    return [
        DropdownInput(
            name="tool_policy",
            display_name="Tool permissions",
            options=["tool_defaults", "ask", "deny"],
            value="tool_defaults",
            info=(
                "Use each tool's approval settings, require approval for every tool call, or block all tools. "
                "Approvals require Agent message output and a resumable run."
            ),
        ),
        DropdownInput(
            name="context_strategy",
            display_name="Context preparation",
            options=["all", "recent_turns"],
            value="all",
            info="Use all loaded messages, or select recent complete turns before each model call.",
        ),
        IntInput(
            name="context_turns",
            display_name="Recent turns",
            value=8,
            range_spec=RangeSpec(min=1, max=10000, step=1, step_type="int"),
            info=(
                "Keep this many complete user turns, including replies and tool results. Stored history stays intact."
            ),
        ),
        DropdownInput(
            name="compaction",
            display_name="Compaction",
            options=["off", "summarize"],
            value="off",
            info=(
                "Summarize older messages with the selected model at the token threshold. "
                "Summary calls incur model usage."
            ),
        ),
        IntInput(
            name="compaction_trigger_tokens",
            display_name="Summarize at estimated tokens",
            value=8000,
            range_spec=RangeSpec(min=1, max=10000000, step=1, step_type="int"),
            info="Approximate token threshold in the loaded conversation. Applies when compaction is summarize.",
        ),
        IntInput(
            name="compaction_keep_messages",
            display_name="Keep recent messages",
            value=12,
            range_spec=RangeSpec(min=1, max=10000, step=1, step_type="int"),
            info="Recent messages kept verbatim during compaction. Tool call/result pairs remain together.",
        ),
        IntInput(
            name="max_iterations",
            display_name="Agent iterations per run",
            value=15,
            range_spec=RangeSpec(min=1, max=128000, step=1, step_type="int"),
            info="Maximum reasoning steps. Provider retries and compaction can make additional model calls.",
        ),
    ]
