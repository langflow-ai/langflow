"""Per-process admission control for ``lfx serve`` flow execution.

A process-wide :class:`asyncio.Semaphore` bounds concurrent flow runs; Prometheus
gauges expose saturation so KEDA can autoscale the fleet and operators can observe
backpressure. The semaphore is per-process, therefore **per worker**: the effective
per-pod ceiling is ``limit x uvicorn workers``. ``limit <= 0`` disables the gate
(unbounded — today's behavior).
"""

from __future__ import annotations

import asyncio
import math
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

# Defaults mirror the chart contract (see the design spec).
_DEFAULT_LIMIT = 0
_DEFAULT_TIMEOUT = 5.0
_DEFAULT_PROFILE = "unknown"

# Gauges live on the default registry and are defined once at import. The ``profile``
# label lets one Prometheus job distinguish editor/serve deployments.
BUILD_SLOTS_LIMIT = Gauge(
    "build_slots_limit",
    "Configured max concurrent flow runs per worker process (0 = no cap).",
    ["profile"],
)
BUILD_SLOTS_IN_USE = Gauge(
    "build_slots_in_use",
    "Flow runs currently holding an execution slot in this worker process.",
    ["profile"],
)


class AdmissionTimeout(Exception):  # noqa: N818
    """Raised when no execution slot frees within the admission timeout."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("No execution slot available within admission timeout")
        self.retry_after = retry_after


@dataclass(frozen=True)
class BuildAdmissionConfig:
    """Resolved admission knobs (CLI flags / ``LANGFLOW_BUILD_*`` env)."""

    limit: int = _DEFAULT_LIMIT
    timeout: float = _DEFAULT_TIMEOUT
    profile: str = _DEFAULT_PROFILE

    @classmethod
    def from_env(cls) -> BuildAdmissionConfig:
        """Build config from ``LANGFLOW_BUILD_*`` env vars, falling back to defaults."""
        return cls(
            limit=int(os.environ.get("LANGFLOW_BUILD_CONCURRENCY_LIMIT", _DEFAULT_LIMIT)),
            timeout=float(os.environ.get("LANGFLOW_BUILD_ADMISSION_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT)),
            profile=os.environ.get("LANGFLOW_BUILD_PROFILE_LABEL", _DEFAULT_PROFILE),
        )


class BuildAdmissionController:
    """Guards flow execution with a per-process semaphore + saturation metrics."""

    def __init__(self, config: BuildAdmissionConfig) -> None:
        self.limit = config.limit
        self.timeout = config.timeout
        self.profile = config.profile
        self._retry_after = max(1, math.ceil(config.timeout))
        # limit <= 0 => disabled: no semaphore, never blocks (today's behavior).
        self._sem: asyncio.Semaphore | None = asyncio.Semaphore(config.limit) if config.limit > 0 else None
        # Publish the cap and create the in-use series (at 0) for this profile.
        BUILD_SLOTS_LIMIT.labels(profile=self.profile).set(config.limit)
        BUILD_SLOTS_IN_USE.labels(profile=self.profile).set(0)

    async def acquire(self) -> None:
        """Acquire a slot, waiting up to ``timeout``; raise ``AdmissionTimeout`` on timeout.

        ``in_use`` is incremented only AFTER a slot is held, so a timed-out (429)
        request is never counted and ``in_use`` can never exceed ``limit``.

        The acquire runs as a shielded task so a ``wait_for`` timeout (or a caller
        cancellation) cannot strand a permit grabbed at the instant of cancellation
        — if the task acquired despite the cancel, the permit is handed back before
        raising. This makes the gate leak-free across the full supported CPython
        range (incl. an unpatched 3.10.0 ``wait_for`` race).
        """
        if self._sem is not None:
            acquire_task = asyncio.ensure_future(self._sem.acquire())
            try:
                await asyncio.wait_for(asyncio.shield(acquire_task), self.timeout)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                await self._discard_acquire(acquire_task)
                raise AdmissionTimeout(self._retry_after) from exc
            except asyncio.CancelledError:
                await self._discard_acquire(acquire_task)
                raise
        BUILD_SLOTS_IN_USE.labels(profile=self.profile).inc()

    async def _discard_acquire(self, acquire_task: asyncio.Future) -> None:
        """Cancel a pending acquire; if it already succeeded, release the permit so it does not leak."""
        acquire_task.cancel()
        try:
            await acquire_task
        except asyncio.CancelledError:
            return  # the permit was never acquired
        # The task completed (permit held) despite the cancel → give it back.
        self._sem.release()

    def release(self) -> None:
        """Release a held slot. Call exactly once per successful ``acquire()``."""
        BUILD_SLOTS_IN_USE.labels(profile=self.profile).dec()
        if self._sem is not None:
            self._sem.release()

    @asynccontextmanager
    async def slot(self):
        """Hold a slot for the block; release on success, exception, or cancellation."""
        await self.acquire()
        try:
            yield
        finally:
            self.release()


def render_metrics() -> tuple[bytes, str]:
    """Return ``(body, content_type)`` in Prometheus exposition format."""
    return generate_latest(), CONTENT_TYPE_LATEST
