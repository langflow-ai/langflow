"""Profile-driven Locust load shape."""

from __future__ import annotations

from locust import LoadTestShape

from tests.locust.langflow_runtime.config.context import RunContext
from tests.locust.langflow_runtime.shapes.drain import drain_remaining_s, drain_tracked_work, stop_new_arrivals
from tests.locust.langflow_runtime.shapes.overture import phase_for_tick, run_overture_hooks


class ProfileLoadShape(LoadTestShape):
    """Drive warm-up, measured steps, and drain from a movement profile."""

    phase: str = "overture"

    def __init__(self) -> None:
        super().__init__()
        self._step_index = 0
        self._measured_started_at: float | None = None
        self._last_user_count = 1

    def _context(self) -> RunContext | None:
        return getattr(self.runner.environment, "run_context", None)

    def tick(self) -> tuple[int, float] | tuple[int, float, list[str] | None] | None:
        context = self._context()
        if context is None:
            return None

        environment = self.runner.environment
        windows = context.profile.windows
        runtime = self.get_run_time()
        warm_up_s = windows.warm_up.duration_s
        measured_s = sum(step.duration_s for step in windows.measured_steps)
        total_s = warm_up_s + measured_s + windows.drain.deadline_s

        self.phase = phase_for_tick(runtime, warm_up_s, measured_s)
        environment.perf_phase = self.phase

        if runtime >= total_s:
            return None

        if runtime < warm_up_s:
            run_overture_hooks(environment, phase="overture")
            users = windows.warm_up.users
            self._last_user_count = max(1, users) if users else self._last_user_count
            return users, windows.warm_up.duration_s

        measured_elapsed = runtime - warm_up_s
        if measured_elapsed < measured_s:
            step = self._current_measured_step(measured_elapsed)
            if step.users is not None:
                self._last_user_count = max(1, step.users)
                return step.users, step.spawn_rate
            rate = step.arrival_rate_per_s or 1.0
            users = max(1, int(rate))
            self._last_user_count = users
            return users, step.spawn_rate

        # Coda: stop new arrivals but keep observers alive until drain deadline.
        stop_new_arrivals(environment, enabled=True)
        remaining = drain_remaining_s(runtime, total_s)
        if remaining <= 0:
            return None
        self._kick_drain_once(environment, remaining)
        return max(1, self._last_user_count), 1.0

    def _kick_drain_once(self, environment, deadline_s: float) -> None:
        if getattr(environment, "perf_drain_started", False):
            return
        environment.perf_drain_started = True

        def _run() -> None:
            drain_tracked_work(environment, deadline_s)

        try:
            import gevent

            gevent.spawn(_run)
        except ImportError:  # pragma: no cover
            _run()

    def _current_measured_step(self, measured_elapsed: float):
        offset = 0.0
        for step in self._context().profile.windows.measured_steps:
            if measured_elapsed < offset + step.duration_s:
                return step
            offset += step.duration_s
        return self._context().profile.windows.measured_steps[-1]
