"""Load-shape phase helpers for the V1 performance suite."""

from __future__ import annotations

import logging
from typing import Any, Literal

PhaseName = Literal["overture", "measured", "coda"]

logger = logging.getLogger(__name__)


def phase_for_tick(elapsed_s: float, overture_s: float, measured_s: float) -> PhaseName:
    """Return the movement phase for a given elapsed runtime."""
    if elapsed_s < overture_s:
        return "overture"
    if elapsed_s < overture_s + measured_s:
        return "measured"
    return "coda"


def run_overture_hooks(environment: Any, *, phase: PhaseName = "overture") -> None:
    """Optional overture hooks — mark phase; warm-up load is shape-driven."""
    environment.perf_phase = phase
    logger.debug("perf phase -> %s", phase)
