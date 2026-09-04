"""Injected pause-probe seam (LE-1440).

The graph never imports langflow: the runtime (LE-1442) injects a probe that
consults the job's durable signals and answers with a control decision. The
default no-op keeps standalone lfx running without ever pausing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

PauseDecision = Literal["run", "pause", "cancel"]
PauseProbe = Callable[[str], Awaitable[str]]

RUN: PauseDecision = "run"
PAUSE: PauseDecision = "pause"
CANCEL: PauseDecision = "cancel"


async def noop_pause_probe(_job_id: str) -> str:
    return RUN
