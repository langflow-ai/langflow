"""Bounded sleep isolator for the performance suite queue fixtures."""

from __future__ import annotations

import time

from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.message import Message

# Hard ceiling so a misconfigured profile cannot stall workers indefinitely.
_MAX_DURATION_MS = 5_000


class PerfSleep(Component):
    """Sleep for a bounded duration and return a deterministic result."""

    display_name = "Perf Sleep"
    description = "Bounded sleep isolator for performance-suite background-queue fixtures."
    name = "PerfSleep"
    icon = "timer"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Opaque payload echoed into the deterministic result.",
            value="ping",
        ),
        IntInput(
            name="duration_ms",
            display_name="Duration ms",
            info=f"Sleep duration in milliseconds (capped at {_MAX_DURATION_MS}).",
            value=50,
            range_spec=RangeSpec(min=1, max=_MAX_DURATION_MS, step=1, step_type="int"),
        ),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="run"),
    ]

    def run(self) -> Message:
        duration_ms = max(1, min(int(self.duration_ms or 1), _MAX_DURATION_MS))
        time.sleep(duration_ms / 1000.0)
        text = getattr(self.input_value, "text", None) or str(self.input_value)
        return Message(text=f"slept:{duration_ms}:{text}")
