"""FormatResult component - formats tool results back into the message history.

This component takes the original messages, the AI message with tool_calls,
and the tool results, then formats them into a proper message list that can
be sent back to CallModel for the next iteration.
"""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, Output
from lfx.schema.dataframe import DataFrame


class FormatResultComponent(Component):
    """Formats tool results as messages for the next LLM call.

    This component:
    1. Takes the original conversation messages (as DataFrame or Message list)
    2. Extracts the AI message data from tool_results (passed through from ExecuteTool)
    3. Appends the AI message (with tool_calls)
    4. Appends ALL tool result messages from ExecuteTool
    5. Returns the updated message DataFrame

    The output connects back to CallModel to continue the agent loop.
    """

    display_name = "Format Result"
    description = "Format tool results as messages for the next model call."
    icon = "file-text"
    category = "agent_blocks"

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Initial user input (Message). Used on first iteration.",
            input_types=["Message"],
            required=False,
        ),
        HandleInput(
            name="messages",
            display_name="Message History",
            info="Conversation history as DataFrame. Used in loop iterations.",
            input_types=["DataFrame"],
            required=False,
        ),
        HandleInput(
            name="tool_results",
            display_name="Tool Results",
            info="The results from ExecuteTool (list of Data objects). First result contains AI message data.",
            input_types=["Data"],
            is_list=True,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Messages",
            name="updated_messages",
            method="format_result",
        ),
    ]

    def format_result(self) -> DataFrame:
        """Format the tool results and return as a DataFrame.

        Returns a DataFrame containing all conversation context:
        original messages, AI message, and all tool results.
        """
        from lfx.schema.data import Data

        # Start with original messages as list of dicts
        message_rows: list[dict] = []

        # Check if we have messages DataFrame (from loop iteration)
        if self.messages is not None and isinstance(self.messages, DataFrame) and not self.messages.empty:
            # Use messages from DataFrame (loop iteration)
            message_rows.extend(self.messages.to_dict(orient="records"))
        elif self.input_value:
            from lfx.schema.message import Message

            # First call - use input_value as the user message
            # input_value is a Message (from HandleInput)
            if isinstance(self.input_value, Message):
                message_rows.append(
                    {
                        "text": self.input_value.text or "",
                        "sender": self.input_value.sender or "User",
                        "sender_name": self.input_value.sender_name or "",
                        "tool_calls": None,
                        "has_tool_calls": False,
                        "tool_call_id": None,
                        "is_tool_result": False,
                    }
                )
            else:
                # Fallback for string input
                message_rows.append(
                    {
                        "text": str(self.input_value),
                        "sender": "User",
                        "sender_name": "",
                        "tool_calls": None,
                        "has_tool_calls": False,
                        "tool_call_id": None,
                        "is_tool_result": False,
                    }
                )

        # Extract AI message data from first tool result (passed through from ExecuteTool)
        results = self.tool_results if isinstance(self.tool_results, list) else [self.tool_results]
        ai_message_text = ""
        ai_message_tool_calls = None
        if results and results[0] is not None:
            first_result = results[0]
            if isinstance(first_result, Data):
                ai_message_text = first_result.data.get("ai_message_text", "")
                ai_message_tool_calls = first_result.data.get("ai_message_tool_calls")

        # Add the AI message row
        if ai_message_tool_calls is not None:
            ai_row = {
                "text": ai_message_text,
                "sender": "Machine",
                "sender_name": "AI",
                "tool_calls": ai_message_tool_calls,
                "has_tool_calls": True,
                "tool_call_id": None,
                "is_tool_result": False,
            }
            message_rows.append(ai_row)

        # Add all tool result messages (results already assigned above)
        tool_count = 0
        for result in results:
            if result is None:
                continue
            # Handle Data object
            if isinstance(result, Data):
                tool_call_id = result.data.get("tool_call_id", "")
                tool_name = result.data.get("tool_name", "unknown")

                # Get the result content
                if "error" in result.data:
                    content = f"Error: {result.data['error']}"
                else:
                    result_value = result.data.get("result", "")
                    content = self._format_result_content(result_value)

                # Create a tool result row
                tool_row = {
                    "text": content,
                    "sender": "Tool",
                    "sender_name": tool_name,
                    "tool_calls": None,
                    "has_tool_calls": False,
                    "tool_call_id": tool_call_id,
                    "is_tool_result": True,
                }
                message_rows.append(tool_row)
                tool_count += 1

        self.log(f"Formatted {len(message_rows)} message(s) with {tool_count} tool result(s)")

        # Return as DataFrame
        return DataFrame(message_rows)

    def _format_result_content(self, result: Any) -> str:
        """Format a tool result as a string."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            import json

            return json.dumps(result, indent=2)
        if isinstance(result, list):
            import json

            return json.dumps(result, indent=2)
        return str(result)
