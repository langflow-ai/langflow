"""CheckDone component - routes based on whether AI response has tool_calls.

This component checks if the AI message contains tool_calls and routes accordingly:
- If tool_calls are present: routes to "continue" output (agent should execute tools)
- If no tool_calls: routes to "done" output (agent loop can finish)
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageInput, Output
from lfx.schema.message import Message


class CheckDoneComponent(Component):
    """Routes messages based on whether tool_calls are present.

    This component examines an AI message and routes it to one of two outputs:
    - "done": The AI has finished (no tool_calls) - exit the agent loop
    - "continue": The AI wants to call tools - continue the agent loop

    Use this after CallModel to implement the agent loop control flow.
    """

    display_name = "Check Done"
    description = "Route based on whether the AI wants to call tools or has finished."
    icon = "git-branch"
    category = "agent_blocks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__iteration_updated = False

    inputs = [
        MessageInput(
            name="ai_message",
            display_name="AI Message",
            info="The AI message from CallModel to check for tool_calls.",
            required=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="Maximum number of tool-calling iterations before forcing done.",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Done",
            name="done",
            method="done_response",
            group_outputs=True,
        ),
        Output(
            display_name="Continue",
            name="continue_output",
            method="continue_response",
            group_outputs=True,
        ),
    ]

    def _pre_run_setup(self):
        self.__iteration_updated = False

    def _has_tool_calls(self) -> bool:
        """Check if the AI message has tool_calls."""
        if self.ai_message is None:
            return False

        # Check the data dict for tool_calls (set by CallModel)
        if hasattr(self.ai_message, "data") and self.ai_message.data:
            if self.ai_message.data.get("has_tool_calls", False):
                return True
            if self.ai_message.data.get("tool_calls"):
                return True

        return False

    def _iterate_and_stop_once(self, route_to_stop: str):
        """Handle iteration counting and conditional routing."""
        if not self.__iteration_updated:
            self.update_ctx({f"{self._id}_iteration": self.ctx.get(f"{self._id}_iteration", 0) + 1})
            self.__iteration_updated = True

            current_iteration = self.ctx.get(f"{self._id}_iteration", 0)

            # If max iterations reached, force the done output
            if current_iteration >= self.max_iterations and route_to_stop == "done":
                # Clear exclusions and switch routes
                if self._id in self.graph.conditional_exclusion_sources:
                    previous_exclusions = self.graph.conditional_exclusion_sources[self._id]
                    self.graph.conditionally_excluded_vertices -= previous_exclusions
                    del self.graph.conditional_exclusion_sources[self._id]

                route_to_stop = "continue_output"
                self.stop(route_to_stop)
                return

            # Normal case
            self.stop(route_to_stop)
            self.graph.exclude_branch_conditionally(self._id, output_name=route_to_stop)

    def done_response(self) -> Message:
        """Output when the AI has finished (no tool_calls)."""
        has_tools = self._has_tool_calls()

        # Check if forced due to max iterations
        current_iteration = self.ctx.get(f"{self._id}_iteration", 0)
        force_done = current_iteration >= self.max_iterations

        if not has_tools or force_done:
            # No tool calls - AI is done
            self.log("No tool calls - AI is done")
            if not force_done:
                self._iterate_and_stop_once("continue_output")
            return self.ai_message

        # Has tool calls - stop this branch
        self._iterate_and_stop_once("done")
        return Message(text="")

    def continue_response(self) -> Message:
        """Output when the AI wants to call tools."""
        has_tools = self._has_tool_calls()

        if has_tools:
            # Has tool calls - continue to tool execution
            self.log("Tool calls present - continuing loop")
            self._iterate_and_stop_once("done")
            return self.ai_message

        # No tool calls - stop this branch
        self._iterate_and_stop_once("continue_output")
        return Message(text="")
