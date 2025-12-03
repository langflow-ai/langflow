"""WhileLoop component - manages iteration for agent loops.

This component manages the iteration cycle for agent workflows.
It passes data to the loop body and continues until max_iterations or
the loop body stops producing output.

Flow pattern:
ChatInput → WhileLoop → CallModel → [Tool Calls] → ExecuteTool → FormatResult
                ↑                                                      ↓
                +------------------------------------------------------+
                         ↓ (CallModel ai_message - done)
                    ChatOutput
"""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput, IntInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output


class WhileLoopComponent(Component):
    """Manages iteration for agent loops.

    This component enables visual agent loops by:
    1. Passing initial input to the loop body (CallModel)
    2. Continuing iterations until max_iterations or loop body stops
    3. Enforcing max_iterations as a safety limit

    The loop stops when:
    - max_iterations is reached
    - CallModel's ai_message output fires (no tool calls)
    """

    display_name = "While Loop"
    description = "Manages iteration for agent loops. Connect to CallModel."
    icon = "repeat"

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Initial Input",
            info="The initial input (Message) to pass to the first iteration.",
            input_types=["DataFrame", "Data", "Message"],
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="Maximum number of iterations to prevent infinite loops.",
            value=10,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Loop",
            name="loop",
            method="loop_output",
            allows_loop=True,
            loop_types=["DataFrame"],
            info="Connect to CallModel. Outputs DataFrame for each iteration.",
        ),
    ]

    def _to_dataframe(self, value: Any) -> DataFrame:
        """Convert input value to DataFrame."""
        if isinstance(value, DataFrame):
            return value
        if isinstance(value, Data):
            return DataFrame([value])
        if isinstance(value, dict):
            return DataFrame([Data(data=value)])
        if isinstance(value, Message):
            # Convert Message to DataFrame row with all fields
            msg_data = {
                "text": value.text or "",
                "sender": value.sender or "User",
                "sender_name": value.sender_name or "",
            }
            # Preserve data dict from Message
            if value.data:
                msg_data.update(value.data)
            return DataFrame([msg_data])
        if hasattr(value, "text"):
            # Message-like object - preserve its data attributes
            msg_data = {
                "text": str(value.text) if value.text else "",
                "sender": getattr(value, "sender", "User"),
            }
            # Preserve data dict from Message
            if hasattr(value, "data") and value.data:
                msg_data.update(value.data)
            return DataFrame([msg_data])
        return DataFrame([Data(text=str(value))])

    def _get_loop_feedback(self) -> Any | None:
        """Get the feedback value from the loop connection if available.

        When FormatResult connects to the 'loop' output (allows_loop=True),
        the graph resolves the source vertex's result and passes it directly
        to _attributes["loop"]. This happens after FormatResult has been built.

        Returns:
            The feedback DataFrame from FormatResult, or None if not available.
        """
        # Check if there's a loop feedback value in _attributes
        loop_value = self._attributes.get("loop")

        if loop_value is None:
            return None

        # The graph resolves the source vertex's result, so loop_value
        # is already the DataFrame (or other value) from FormatResult
        if isinstance(loop_value, DataFrame):
            return loop_value

        # Handle other potential value types
        if hasattr(loop_value, "built"):
            # It's a Vertex - get its result
            if loop_value.built and loop_value.results:
                for result in loop_value.results.values():
                    if result is not None:
                        return result
            if loop_value.built and loop_value.built_object is not None:
                return loop_value.built_object

        return None

    def loop_output(self) -> DataFrame:
        """Output the input value as DataFrame to the loop body.

        On first iteration: uses input_value (from ChatInput)
        On subsequent iterations: uses loop feedback (from FormatResult)

        The feedback is connected to the 'loop' output which has allows_loop=True.
        When FormatResult builds, its result is available via the loop vertex.
        """
        # Check for loop feedback first (subsequent iterations)
        feedback = self._get_loop_feedback()
        if feedback is not None:
            return self._to_dataframe(feedback)

        # First iteration: use input_value
        return self._to_dataframe(self.input_value)
