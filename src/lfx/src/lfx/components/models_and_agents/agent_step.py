"""AgentStep: one model call of an agent loop.

Takes the history, makes one call through the harness loop runtime and returns the history the call rewrote,
which ends in the model's message, on `tool_calls`. `ai_message` is the answer, and its branch stops when the
model asked for tools.

WhileLoop -> AgentStep -[tool_calls]-> ExecuteTool -> WhileLoop
                       -[ai_message]-> the answer
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from lfx.base.agents.loop_rows import messages_to_rows, rows_to_messages
from lfx.base.agents.loop_runtime import HarnessLoopRuntime
from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.components.models_and_agents.agent_helpers.loop_blocks import block_call, block_tools
from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, ModelInput, MultilineInput, Output, SecretStrInput
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict  # noqa: TC001
from lfx.schema.message import Message


class AgentStepComponent(Component):
    display_name = "Agent Step"
    description = "One model call of an agent loop. Outputs to Response (done) or Tool Calls (continue the loop)."
    icon = "brain"
    beta = True

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider. Ignored when the loop runs inside a harness, which brings its own model.",
            real_time_refresh=True,
            required=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            required=False,
            show=True,
            real_time_refresh=True,
            advanced=True,
        ),
        HandleInput(
            name="messages",
            display_name="Messages",
            info="The conversation so far, one row per message.",
            input_types=["DataFrame"],
            required=True,
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Optional system message to set the behavior of the assistant.",
            advanced=False,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            info="Tools the model may call. Execute Tool must get the same tools.",
            input_types=["Tool"],
            is_list=True,
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="ai_message", method="get_ai_message", group_outputs=True),
        Output(display_name="Tool Calls", name="tool_calls", method="get_tool_calls", group_outputs=True),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        return update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="agent_step_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

    def _pre_run_setup(self):
        super()._pre_run_setup()
        self._step_result = None

    def _own_runtime(self) -> HarnessLoopRuntime:
        return HarnessLoopRuntime(
            model=get_llm(model=self.model, user_id=self.user_id, api_key=self.api_key, stream=True),
            tools=block_tools(self.tools),
            system_prompt=self.system_message or None,
            middleware=[],
        )

    async def _call_model(self) -> tuple[list[BaseMessage], Message]:
        """The one model call of this build. `ai_message` and `tool_calls` both read it."""
        if self._step_result is None:
            self._step_result = await block_call(
                self, self._own_runtime, rows_to_messages(self.messages), lambda runtime, h: runtime.model_call(h)
            )
        return self._step_result

    async def get_ai_message(self) -> Message:
        """The final answer. Stops this branch when the model asked for tools."""
        history, message = await self._call_model()
        if history and isinstance(history[-1], AIMessage) and history[-1].tool_calls:
            self.stop("ai_message")
            self.graph.exclude_branch_conditionally(self._id, output_name="ai_message")
            return Message(text="")
        return message

    async def get_tool_calls(self) -> DataFrame:
        """The history the model call rewrote, ending in the model's message. It feeds the loop back."""
        history, _ = await self._call_model()
        return DataFrame(messages_to_rows(history))
