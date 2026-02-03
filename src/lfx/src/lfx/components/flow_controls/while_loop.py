"""WhileLoop component - executes loop body until termination condition.

Uses subgraph execution pattern for proper isolation and event streaming.

Flow pattern (agent example):
MessageHistory → WhileLoop.initial_state (past conversations)
ChatInput → WhileLoop.input_value (current message)
WhileLoop.loop → AgentStep → [tool_calls] → ExecuteTool → WhileLoop.loop (feedback)
                          → [ai_message] → ChatOutput (terminates loop)
WhileLoop.done → (outputs final accumulated state)
"""

from __future__ import annotations

from typing import Any

from lfx.base.flow_controls.loop_utils import (
    get_loop_body_start_edge,
    get_loop_body_start_vertex,
    get_loop_body_vertices,
)
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput, IntInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output


class WhileLoopComponent(Component):
    """Executes loop body repeatedly with state accumulation.

    Uses subgraph execution for proper isolation and event streaming.
    The loop body is executed as an isolated subgraph for each iteration.

    Termination conditions:
    - max_iterations is reached
    - Loop body produces no feedback (branch stopped, e.g., ai_message instead of tool_calls)
    - Error in loop body execution
    """

    display_name = "While Loop"
    description = "Executes loop body repeatedly with state accumulation until termination."
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
            info="The input for the first iteration. Combined with initial_state.",
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
            info="Connect to loop body (e.g., AgentStep). Receives feedback from loop end.",
            group_outputs=True,
        ),
        Output(
            display_name="Done",
            name="done",
            method="done_output",
            info="Outputs final accumulated state when loop terminates.",
            group_outputs=True,
        ),
    ]

    def _to_dataframe(self, value: Any) -> DataFrame:
        """Convert input value to DataFrame."""
        if isinstance(value, DataFrame):
            return value
        if isinstance(value, list):
            # List of dicts (e.g., from ExecuteTool) - create DataFrame directly
            # This preserves all columns including _agent_message_id
            return DataFrame(value)
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

    def get_loop_body_vertices(self) -> set[str]:
        """Identify vertices in this loop's body via graph traversal.

        Traverses from the loop's "loop" output to the vertex that feeds back
        to the loop's "loop" input, collecting all vertices in between.

        Returns:
            Set of vertex IDs that form this loop's body
        """
        if not hasattr(self, "_vertex") or self._vertex is None:
            return set()

        return get_loop_body_vertices(
            vertex=self._vertex,
            graph=self.graph,
            get_incoming_edge_by_target_param_fn=self.get_incoming_edge_by_target_param,
            loop_output_name="loop",
            feedback_input_name="loop",
        )

    def _get_loop_body_start_vertex(self) -> str | None:
        """Get the first vertex in the loop body (connected to loop's output).

        Returns:
            The vertex ID of the first vertex in the loop body, or None if not found
        """
        if not hasattr(self, "_vertex") or self._vertex is None:
            return None

        return get_loop_body_start_vertex(vertex=self._vertex, loop_output_name="loop")

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

    def _extract_loop_output(self, results: list) -> DataFrame | None:
        """Extract the output from subgraph execution results.

        Looks for the result from the vertex that feeds back to the loop input.
        If that vertex didn't produce output (e.g., branch was stopped), returns None.

        Args:
            results: List of VertexBuildResult objects from subgraph execution

        Returns:
            DataFrame containing the loop iteration output, or None if no feedback
        """
        if not results:
            return None

        # Get the vertex ID that feeds back to the loop input (end of loop body)
        # Requires vertex context to find the incoming edge
        if not hasattr(self, "_vertex") or self._vertex is None:
            return None

        end_vertex_id = self.get_incoming_edge_by_target_param("loop")

        if not end_vertex_id:
            return None

        # Find the result for the end vertex
        for result in results:
            if (
                hasattr(result, "vertex")
                and result.vertex.id == end_vertex_id
                and hasattr(result, "result_dict")
                and result.result_dict.outputs
            ):
                # Get first output value
                first_output = next(iter(result.result_dict.outputs.values()))

                # Handle both dict (from model_dump()) and object formats
                value = None
                if isinstance(first_output, dict) and "message" in first_output:
                    value = first_output["message"]
                elif hasattr(first_output, "message"):
                    value = first_output.message
                else:
                    value = first_output

                if value is not None:
                    return self._to_dataframe(value)

        # End vertex didn't produce output - loop body stopped (termination condition)
        return None

    async def execute_loop(self) -> DataFrame:
        """Execute the loop body repeatedly until termination.

        Creates an isolated subgraph for the loop body and executes it
        for each iteration, accumulating state until termination.

        Returns:
            Final accumulated DataFrame after loop terminates
        """
        # Get event_manager from component (set via set_event_manager)
        event_manager = self._event_manager
        # Get the loop body configuration once
        loop_body_vertex_ids = self.get_loop_body_vertices()
        start_vertex_id = self._get_loop_body_start_vertex()
        start_edge = get_loop_body_start_edge(self._vertex, loop_output_name="loop")

        if not loop_body_vertex_ids:
            # No loop body connected - just return initial state
            return self._build_initial_state()

        # Initialize accumulated state
        accumulated_state = self._build_initial_state()

        for iteration in range(self.max_iterations):
            # Create fresh subgraph for each iteration using async context manager
            async with self.graph.create_subgraph(loop_body_vertex_ids) as iteration_subgraph:
                # Get the target parameter name from the edge
                target_param = "messages"  # default
                if start_vertex_id and start_edge and start_edge.target_handle:
                    target_param = getattr(start_edge.target_handle, "field_name", "messages")

                    # Inject accumulated state into vertex data BEFORE preparing
                    # This ensures components have data during build/validation
                    for vertex_data in iteration_subgraph._vertices:  # noqa: SLF001
                        if vertex_data.get("id") == start_vertex_id:
                            if "data" in vertex_data and "node" in vertex_data["data"]:
                                template = vertex_data["data"]["node"].get("template", {})
                                if target_param in template:
                                    template[target_param]["value"] = accumulated_state
                            break

                iteration_subgraph.prepare()

                # Also set the value in the vertex's raw_params after prepare
                # This ensures the value is available during component build
                if start_vertex_id and start_edge:
                    start_vertex = iteration_subgraph.get_vertex(start_vertex_id)
                    if start_vertex:
                        start_vertex.update_raw_params({target_param: accumulated_state}, overwrite=True)

                # Store reference to parent graph so subgraph can delegate ChatOutput checks
                # This allows components in the subgraph to correctly determine if they're
                # connected to ChatOutput by checking the parent graph's connections
                iteration_subgraph._parent_graph = self.graph  # noqa: SLF001

                # If WhileLoop is connected to ChatOutput (via "done" output), mark the subgraph
                # so that components inside know they should store/stream messages
                if self.is_connected_to_chat_output():
                    iteration_subgraph._stream_to_playground = True  # noqa: SLF001

                # Execute subgraph and collect results
                # Pass event_manager so UI receives events from subgraph execution
                results = []
                async for result in iteration_subgraph.async_start(event_manager=event_manager):
                    results.append(result)
                    # Stop on error
                    if hasattr(result, "valid") and not result.valid:
                        from lfx.log.logger import logger

                        await logger.aerror(f"Error in loop iteration {iteration}: {result}")
                        return accumulated_state

                # Extract output from this iteration
                iteration_output = self._extract_loop_output(results)

                if iteration_output is None:
                    # No feedback output - loop body took a different branch (termination)
                    # This happens when e.g. AgentStep outputs ai_message instead of tool_calls
                    break

            # Accumulate: existing state + new data from loop body
            new_rows = iteration_output.to_dict(orient="records")
            accumulated_state = accumulated_state.add_rows(new_rows)

        return accumulated_state

    def loop_output(self) -> DataFrame:
        """Loop output is handled internally by subgraph execution.

        This method stops the branch as the actual loop execution
        happens in done_output() via subgraph iteration.
        """
        self.stop("loop")
        return DataFrame([])

    async def done_output(self) -> DataFrame:
        """Execute the loop and return final accumulated state.

        This is the main execution point for the while loop. It:
        1. Builds initial state from inputs
        2. Executes loop body as isolated subgraph for each iteration
        3. Accumulates state until termination condition
        4. Returns final accumulated state

        Returns:
            Final accumulated DataFrame after loop terminates
        """
        try:
            return await self.execute_loop()
        except Exception as e:
            from lfx.log.logger import logger

            await logger.aerror(f"Error executing while loop: {e}")
            raise
