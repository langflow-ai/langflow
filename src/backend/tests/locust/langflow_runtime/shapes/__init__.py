"""Load shapes for the performance suite."""

from tests.locust.langflow_runtime.shapes.drain import (
    drain_remaining_s,
    drain_tracked_work,
    reset_movement_state,
    stop_new_arrivals,
)
from tests.locust.langflow_runtime.shapes.overture import phase_for_tick, run_overture_hooks

# ProfileLoadShape imports Locust; keep it out of the package import surface for unit tests.
__all__ = [
    "ProfileLoadShape",
    "drain_remaining_s",
    "drain_tracked_work",
    "phase_for_tick",
    "reset_movement_state",
    "run_overture_hooks",
    "stop_new_arrivals",
]


def __getattr__(name: str):
    if name == "ProfileLoadShape":
        from tests.locust.langflow_runtime.shapes.profile import ProfileLoadShape

        return ProfileLoadShape
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
