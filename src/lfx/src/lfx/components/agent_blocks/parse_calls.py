"""ParseCalls component - extracts tool calls from an AI message.

This component extracts all tool_calls from an AI message and outputs them
as a list of Data objects. Useful for inspecting or debugging tool calls.

Note: ExecuteTool can take the AI message directly and extract tool calls
internally. This component is optional and useful for debugging/inspection.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output
from lfx.schema.data import Data


class ParseCallsComponent(Component):
    """Extracts all tool calls from an AI message.

    This component parses the AI message to extract all tool_calls and outputs them
    as a list of Data objects containing the tool name and arguments.

    Each tool call is output as a Data object with:
    - name: The name of the tool to call
    - args: The arguments to pass to the tool
    - id: The tool call ID (for matching results back to calls)

    Note: ExecuteTool can accept the AI message directly. This component is
    optional and useful for debugging or inspecting tool calls.
    """

    display_name = "Parse Calls"
    description = "Extract all tool calls from an AI message for inspection."
    icon = "braces"
    category = "agent_blocks"

    inputs = [
        MessageInput(
            name="ai_message",
            display_name="AI Message",
            info="The AI message containing tool_calls to extract.",
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Tool Calls",
            name="tool_calls",
            method="parse_calls",
        ),
    ]

    def parse_calls(self) -> list[Data]:
        """Extract all tool calls from the AI message."""
        if self.ai_message is None:
            return [Data(data={"error": "No AI message provided"})]

        # Get tool_calls from message data (set by CallModel)
        raw_tool_calls = []
        if hasattr(self.ai_message, "data") and self.ai_message.data:
            raw_tool_calls = self.ai_message.data.get("tool_calls", [])

        if not raw_tool_calls:
            return [Data(data={"error": "No tool calls found in AI message"})]

        results = []
        for tc in raw_tool_calls:
            # Handle both dict format and object format
            if isinstance(tc, dict):
                tool_call_data = Data(
                    data={
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "tool_call"),
                    }
                )
            else:
                # Object with attributes
                tool_call_data = Data(
                    data={
                        "name": getattr(tc, "name", ""),
                        "args": getattr(tc, "args", {}),
                        "id": getattr(tc, "id", ""),
                        "type": getattr(tc, "type", "tool_call"),
                    }
                )
            results.append(tool_call_data)

        tool_names = [r.data.get("name", "unknown") for r in results]
        self.log(f"Extracted {len(results)} tool call(s): {', '.join(tool_names)}")
        return results
