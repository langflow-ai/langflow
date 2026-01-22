"""WhileLoop component - manages iteration and state accumulation for loops.

This component manages the iteration cycle for workflows that need accumulation.
It accumulates data across iterations, building up state over time.

Flow pattern (agent example):
MessageHistory → WhileLoop (initial state)
ChatInput → WhileLoop (input)
WhileLoop → AgentStep → [Tool Calls] → ExecuteTool
    ↑                                        ↓
    +----------------------------------------+
                 ↓ (Response - done)
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
    """Manages iteration and state accumulation for loops.

    This component enables visual loops with state accumulation by:
    1. Combining initial state (if provided) with input on first iteration
    2. Accumulating new data from each iteration with existing state
    3. Continuing iterations until max iterations or loop body stops

    The loop stops when:
    - Max iterations is reached
    - A downstream component stops the branch (e.g., Agent Step's Response output)
    """

    display_name = "While Loop"
    description = "Manages iteration and state accumulation for loops."
    icon = "repeat"

    inputs = [
        HandleInput(
            name="initial_state",
            display_name="Initial State",
            info="Optional base state (DataFrame) to prepend to input_value. For agents, connect MessageHistory here.",
            input_types=["DataFrame"],
            required=False,
        ),
        HandleInput(
            name="input_value",
            display_name="Input",
            info="The input to append to initial_state on the first iteration.",
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
            info="Connect to Agent Step. Outputs accumulated DataFrame for each iteration.",
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

    def _get_loop_feedback(self) -> DataFrame | None:
        """Get the feedback value from the loop connection if available.

        When ExecuteTool connects to the 'loop' output (allows_loop=True),
        the graph resolves the source vertex's result and passes it directly
        to _attributes["loop"]. This happens after ExecuteTool has been built.

        Returns:
            The feedback DataFrame from ExecuteTool, or None if not available.
        """
        # Check if there's a loop feedback value in _attributes
        loop_value = self._attributes.get("loop")

        if loop_value is None:
            return None

        # The graph resolves the source vertex's result, so loop_value
        # is already the DataFrame (or other value) from ExecuteTool
        if isinstance(loop_value, DataFrame):
            return loop_value

        # Handle other potential value types
        if hasattr(loop_value, "built"):
            # It's a Vertex - get its result
            if loop_value.built and loop_value.results:
                for result in loop_value.results.values():
                    if result is not None:
                        return self._to_dataframe(result)
            if loop_value.built and loop_value.built_object is not None:
                return self._to_dataframe(loop_value.built_object)

        return None

    def _get_accumulated_state(self) -> DataFrame | None:
        """Get the accumulated state from previous iterations.

        This is stored in _attributes["_accumulated_state"] and persists
        across iterations within the same graph execution.
        """
        return self._attributes.get("_accumulated_state")

    def _set_accumulated_state(self, state: DataFrame) -> None:
        """Set the accumulated state for subsequent iterations."""
        self._attributes["_accumulated_state"] = state

    def _build_initial_state(self) -> DataFrame:
        """Build the initial state by combining initial_state input with input_value.

        If initial_state is provided (e.g., from MessageHistory), it is used as the base
        and input_value is appended to it. Otherwise, just input_value is used.
        """
        input_df = self._to_dataframe(self.input_value)

        # If initial_state is provided, prepend it to input_value
        if (
            self.initial_state is not None
            and isinstance(self.initial_state, DataFrame)
            and not self.initial_state.empty
        ):
            # initial_state comes first (history), then input_value (current)
            input_rows = input_df.to_dict(orient="records")
            return self.initial_state.add_rows(input_rows)

        return input_df

    def loop_output(self) -> DataFrame:
        """Output the accumulated state to the loop body.

        On first iteration: combines initial_state (if any) with input_value
        On subsequent iterations: accumulates loop feedback with existing state

        The feedback is connected to the 'loop' output which has allows_loop=True.
        When the loop body builds, its result is available via feedback.
        We accumulate these with our existing state.
        """
        # Check for loop feedback (subsequent iterations)
        feedback = self._get_loop_feedback()

        if feedback is not None:
            # Get existing accumulated state
            accumulated = self._get_accumulated_state()

            if accumulated is not None:
                # Accumulate: existing state + new data from loop body
                # Use add_rows to maintain DataFrame type
                feedback_rows = feedback.to_dict(orient="records")
                new_state = accumulated.add_rows(feedback_rows)
            else:
                # First feedback but no accumulated state yet - shouldn't happen normally
                # but handle gracefully by building initial state + feedback
                initial = self._build_initial_state()
                feedback_rows = feedback.to_dict(orient="records")
                new_state = initial.add_rows(feedback_rows)

            # Store the new accumulated state
            self._set_accumulated_state(new_state)
            return new_state

        # First iteration: build initial state and store it
        initial_state = self._build_initial_state()
        self._set_accumulated_state(initial_state)
        return initial_state
