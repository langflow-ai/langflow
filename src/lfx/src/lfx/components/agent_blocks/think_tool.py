"""ThinkTool - A tool that enables agent reasoning without ending the loop.

Inspired by Anthropic's "think" tool, this allows agents to pause and reason
through complex problems step-by-step before taking action or responding.

The tool simply returns the thought, which becomes part of the message history.
This keeps the agent loop going while giving the model space to reason about
tool outputs, plan next steps, or work through complex logic.

Usage:
    Connect this tool to CallModel alongside other tools. The agent can call
    think(thought="Let me analyze these results...") to reason without
    triggering a final response.
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output


class ThinkInput(BaseModel):
    """Input schema for the think tool."""

    thought: str = Field(
        description="Your thought process. Use this to reason about tool results, "
        "plan next steps, analyze complex information, or work through multi-step problems."
    )


def think(thought: str) -> str:
    """Think through a problem step-by-step.

    Use this tool to reason about information, plan your approach, or work through
    complex logic before taking action or responding. Your thoughts will be recorded
    but not shown to the user.

    Args:
        thought: Your reasoning or analysis.

    Returns:
        The thought, acknowledged.
    """
    return f"Thought recorded: {thought}"


class ThinkToolComponent(Component):
    """A tool that enables agent reasoning without ending the loop.

    Inspired by Anthropic's "think" tool approach, this gives agents the ability
    to pause and reason through complex problems before taking action.

    When to use:
    - Analyzing complex tool outputs before deciding next steps
    - Planning a multi-step approach to a problem
    - Working through detailed guidelines or policies
    - Making sequential decisions where each step builds on previous ones

    The tool simply echoes the thought back, keeping the agent loop active
    while the reasoning becomes part of the conversation history.
    """

    display_name = "Think Tool"
    description = "Enables agent reasoning without ending the loop. Connect to CallModel's tools input."
    icon = "brain"
    category = "agent_blocks"

    inputs = [
        MultilineInput(
            name="custom_instructions",
            display_name="Custom Instructions",
            info="Optional instructions to include in the tool description for domain-specific guidance.",
            value="",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Tool",
            name="tool",
            method="build_tool",
        ),
    ]

    def build_tool(self) -> StructuredTool:
        """Build the think tool with optional custom instructions."""
        base_description = (
            "Think through a problem step-by-step. Use this tool to reason about "
            "information, plan your approach, or work through complex logic before "
            "taking action or responding. Your thoughts will be recorded but not shown to the user."
        )

        if self.custom_instructions:
            description = f"{base_description}\n\nAdditional guidance:\n{self.custom_instructions}"
        else:
            description = base_description

        return StructuredTool(
            name="think",
            description=description,
            func=think,
            args_schema=ThinkInput,
        )
