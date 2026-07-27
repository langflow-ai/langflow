"""Stub LanguageModelComponent for Natural stubbed Basic Prompting (keeps type name)."""

from __future__ import annotations

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

PERF_MOCK_LLM_MARKER = "PERF_MOCK_LLM"


class LanguageModelComponent(Component):
    """Deterministic chat/completions edge — no provider HTTP.

    Output names/methods match the real Language Model node so starter edges
    (``text_output`` → ``text_response``, ``model_output`` → ``build_model``)
    keep working after code swap.
    """

    display_name = "Language Model"
    description = "Stub Language Model for Natural suite stubbed runs."
    name = "LanguageModelComponent"
    icon = "brain-circuit"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="User input echoed into the stub response.",
            value="perf-natural",
        ),
        MessageTextInput(
            name="system_message",
            display_name="System Message",
            info="Ignored by the stub; accepted for starter wiring.",
            value="",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Model Response", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def _seed(self) -> str:
        return getattr(self.input_value, "text", None) or str(self.input_value or "")

    def text_response(self) -> Message:
        return Message(text=f"{PERF_MOCK_LLM_MARKER}:{self._seed()}")

    def build_model(self) -> FakeListChatModel:
        return FakeListChatModel(responses=[f"{PERF_MOCK_LLM_MARKER}:{self._seed()}"])
