"""Bounded subprocess spawn/exit isolator for the performance suite.

Embedded into ``perf_multiproc_churn`` by ``flows/build_fixtures.py``. Used to
stress process spawn without leaving orphaned workers; covered by unit bounds
and integration workflows tests under ``tests/locust/tests/``.
"""

from __future__ import annotations

import subprocess
import sys

from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.message import Message

# Hard ceilings so a misconfigured profile cannot fork-bomb the host.
_MAX_COUNT = 8
_MAX_TIMEOUT_S = 5
# Deterministic sentinel when a child exceeds timeout_s (not a real OS status).
_TIMEOUT_SENTINEL = -9


class PerfSubprocessChurn(Component):
    """Spawn a bounded number of short-lived subprocesses and return their exit codes.

    Blocking subprocess work is intentional for the multiproc isolator. Langflow runs
    sync ``run()`` via a thread pool; under high concurrency that pool can saturate —
    size generator threads accordingly when profiling this axis.
    """

    display_name = "Perf Subprocess Churn"
    description = "Bounded subprocess spawn/exit pressure for performance-suite multiproc isolators."
    name = "PerfSubprocessChurn"
    icon = "terminal"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Opaque payload echoed into the deterministic result.",
            value="perf-multiproc",
        ),
        IntInput(
            name="count",
            display_name="Subprocess count",
            info=f"Number of short-lived subprocesses to spawn (capped at {_MAX_COUNT}).",
            value=2,
            range_spec=RangeSpec(min=1, max=_MAX_COUNT, step=1, step_type="int"),
        ),
        IntInput(
            name="timeout_s",
            display_name="Timeout seconds",
            info=f"Per-subprocess timeout in seconds (capped at {_MAX_TIMEOUT_S}).",
            value=2,
            advanced=True,
            range_spec=RangeSpec(min=1, max=_MAX_TIMEOUT_S, step=1, step_type="int"),
        ),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="run"),
    ]

    def run(self) -> Message:
        count = max(1, min(int(self.count or 1), _MAX_COUNT))
        timeout_s = max(1, min(int(self.timeout_s or 1), _MAX_TIMEOUT_S))
        seed = getattr(self.input_value, "text", None) or str(self.input_value)
        codes: list[int] = []
        for index in range(count):
            # Tiny, deterministic child: print index and exit 0. No shell.
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", f"print({index})"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
                codes.append(int(completed.returncode))
            except subprocess.TimeoutExpired:
                codes.append(_TIMEOUT_SENTINEL)
        code_csv = ",".join(str(code) for code in codes)
        return Message(text=f"multiproc:{count}:{code_csv}:{seed}")
