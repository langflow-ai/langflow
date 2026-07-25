"""Bounded in-process CPU burn isolator for the performance suite.

Embedded into ``perf_cpu_graph`` (and ensemble fixtures that include CPU work)
by ``flows/build_fixtures.py`` / ``flows/builders.py``. Exercised by unit
bounds checks and live workflows coverage in ``tests/locust/tests/``.
"""

from __future__ import annotations

import hashlib
import time

from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.message import Message

# Hard ceiling so a misconfigured profile cannot pin a core indefinitely.
_MAX_DURATION_MS = 5_000
_MAX_ITERATIONS = 5_000_000


class PerfCpuBurn(Component):
    """Burn CPU for a bounded duration and return a deterministic digest."""

    display_name = "Perf CPU Burn"
    description = "Bounded in-process CPU burn for performance-suite CPU/graph isolators."
    name = "PerfCpuBurn"
    icon = "cpu"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Opaque payload echoed into the deterministic digest.",
            value="perf-cpu",
        ),
        IntInput(
            name="duration_ms",
            display_name="Duration ms",
            info=f"Target burn duration in milliseconds (capped at {_MAX_DURATION_MS}).",
            value=25,
            range_spec=RangeSpec(min=1, max=_MAX_DURATION_MS, step=1, step_type="int"),
        ),
        IntInput(
            name="iterations",
            display_name="Max iterations",
            info=f"Safety bound on hash iterations (capped at {_MAX_ITERATIONS}).",
            value=100_000,
            advanced=True,
            range_spec=RangeSpec(min=1, max=_MAX_ITERATIONS, step=1, step_type="int"),
        ),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="run"),
    ]

    def run(self) -> Message:
        duration_ms = max(1, min(int(self.duration_ms or 1), _MAX_DURATION_MS))
        max_iters = max(1, min(int(self.iterations or 1), _MAX_ITERATIONS))
        seed = getattr(self.input_value, "text", None) or str(self.input_value)
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        deadline = time.perf_counter() + (duration_ms / 1000.0)
        completed = 0
        while completed < max_iters and time.perf_counter() < deadline:
            digest = hashlib.sha256(digest.encode("utf-8")).hexdigest()
            completed += 1
        return Message(text=f"cpu:{duration_ms}:{completed}:{digest[:16]}:{seed}")
