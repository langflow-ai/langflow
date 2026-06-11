"""LLM Context component.

Outputs a ``pipecat.processors.aggregators.llm_context.LLMContext`` — Pipecat's
universal conversation-state container (OpenAI-compatible message format).
"""

import json

from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatContext
from lfx.io import DropdownInput, MultilineInput, Output


class LLMContextComponent(Component):
    display_name = "LLM Context"
    description = "Holds the conversation state (messages + tool choice) shared across the pipeline."
    icon = "Brain"
    name = "LLMContext"
    category = "pipecat"

    inputs = [
        MultilineInput(
            name="initial_messages_json",
            display_name="Initial Messages (JSON)",
            value="[]",
            info=(
                "Optional JSON array of OpenAI-style chat messages used to seed the context. "
                'Example: [{"role": "system", "content": "You are a helpful assistant."}]'
            ),
            advanced=True,
        ),
        DropdownInput(
            name="tool_choice",
            display_name="Tool Choice",
            options=["auto", "none", "required"],
            value="auto",
            info="Forces the LLM's tool-use behavior. 'auto' lets the model decide.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Context",
            name="context",
            method="build_context",
            types=["PipecatContext"],
        ),
    ]

    def build_context(self) -> PipecatContext:
        from pipecat.processors.aggregators.llm_context import LLMContext

        raw = (self.initial_messages_json or "").strip()
        messages = json.loads(raw) if raw else None
        if messages is not None and not isinstance(messages, list):
            msg = "initial_messages_json must be a JSON array of message dicts."
            raise ValueError(msg)

        # tool_choice is left at the default unless the user picks something
        # other than 'auto'; LLMContext's default is NOT_GIVEN.
        if self.tool_choice == "auto":
            return LLMContext(messages=messages)
        return LLMContext(messages=messages, tool_choice=self.tool_choice)
