"""A REAL Langflow component with one observable side effect, in a real module.

Custom components need importable source (``inspect.getsource``), so this lives
in a module file rather than being defined inline in a test. ``increment`` bumps
a process-global counter keyed by ``effect_key`` each time the component builds.
The side-effect-safety proof reads the counter to assert at-most-once (counter
stays 1 after a crash + restart that does NOT re-run) vs requeue (counter hits 2).
"""

from __future__ import annotations

import threading

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

_LOCK = threading.Lock()
SIDE_EFFECTS: dict[str, int] = {}


def reset_side_effects() -> None:
    with _LOCK:
        SIDE_EFFECTS.clear()


def side_effect_count(key: str) -> int:
    with _LOCK:
        return SIDE_EFFECTS.get(key, 0)


class SideEffectComponent(Component):
    """Increments an observable counter exactly once per build."""

    display_name = "Side Effect"
    description = "Increments an observable counter exactly once per build."
    icon = "activity"

    inputs = [
        MessageTextInput(name="effect_key", display_name="Effect Key"),
        MessageTextInput(name="input_value", display_name="Input"),
    ]
    outputs = [Output(display_name="Output", name="output", method="increment")]

    def increment(self) -> Message:
        key = self.effect_key
        with _LOCK:
            SIDE_EFFECTS[key] = SIDE_EFFECTS.get(key, 0) + 1
            count = SIDE_EFFECTS[key]
        return Message(text=f"{key}:{count}")


def build_side_effect_graph(effect_key: str):
    """A real connected graph: ChatInput -> SideEffect -> ChatOutput."""
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.graph import Graph

    chat_input = ChatInput(_id="ChatInput-se")
    chat_input.set(input_value="go")
    effect = SideEffectComponent(_id="SideEffect-se")
    effect.set(effect_key=effect_key, input_value=chat_input.message_response)
    chat_output = ChatOutput(_id="ChatOutput-se")
    chat_output.set(input_value=effect.increment)
    return Graph(start=chat_input, end=chat_output)
