"""Deterministic mock LLM for Natural suite ``external_apis=stubbed`` fixtures."""

from __future__ import annotations

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

PERF_MOCK_LLM_MARKER = "PERF_MOCK_LLM"


class PerfMockLlm(Component):
    """Return a deterministic marker string without calling a provider."""

    display_name = "Perf Mock LLM"
    description = "Stub chat/completions edge for Natural suite stubbed runs."
    name = "PerfMockLlm"
    icon = "bot"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="User input echoed into the stub response.",
            value="perf-natural",
        ),
        MessageTextInput(
            name="marker",
            display_name="Marker",
            info="Stable marker token embedded in the response.",
            value=PERF_MOCK_LLM_MARKER,
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_response", method="text_response"),
    ]

    def text_response(self) -> Message:
        seed = getattr(self.input_value, "text", None) or str(self.input_value or "")
        marker = getattr(self.marker, "text", None) or str(self.marker or PERF_MOCK_LLM_MARKER)
        return Message(text=f"{marker}:{seed}")
